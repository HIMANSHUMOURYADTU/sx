import pandas as pd
import plotly.express as px
import plotly.io as pio
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import io
from itertools import combinations

# Use a visually appealing default template for all charts
pio.templates.default = "plotly_dark"

app = FastAPI()

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory data storage (WARNING: Not for production) ---
df_store = {"df": None}
LOW_CARDINALITY_THRESHOLD = 15

def analyze_columns(df: pd.DataFrame):
    """
    Analyzes dataframe columns for type, missing values, and cardinality.
    This function now relies on the final dtypes after conversion.
    """
    analysis = {}
    total_rows = len(df)
    for col in df.columns:
        missing_count = df[col].isnull().sum()
        missing_percentage = (missing_count / total_rows) * 100 if total_rows > 0 else 0
        unique_count = df[col].nunique()

        col_type = 'categorical' # Default
        # Check for specific types in a defined order
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            col_type = 'datetime'
        elif pd.api.types.is_numeric_dtype(df[col]):
            col_type = 'numeric'
        else:
            col_type = 'categorical'

        analysis[col] = {
            "type": col_type,
            "missing_percentage": round(missing_percentage, 2),
            "unique_count": unique_count,
            "cardinality": "low" if unique_count <= LOW_CARDINALITY_THRESHOLD else "high"
        }
    return analysis

@app.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    date_format: str = Form(None) # NEW: Accept an optional date format string
):
    """Receives, processes, and analyzes the uploaded CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
        df.dropna(axis=1, how='all', inplace=True)

        # --- NEW: Date Conversion Logic ---
        # Before analysis, attempt to convert columns to datetime based on user input
        for col in df.columns:
            # Only attempt conversion on non-numeric columns
            if pd.api.types.is_object_dtype(df[col]):
                try:
                    if date_format:
                        # If a format is provided, use it strictly.
                        df[col] = pd.to_datetime(df[col], format=date_format, errors='raise')
                    else:
                        # If no format, try pandas' automatic inference (original behavior)
                        # Coerce errors to NaT and check if any dates were successfully parsed
                        converted = pd.to_datetime(df[col], errors='coerce')
                        if converted.notna().any():
                           df[col] = pd.to_datetime(df[col], errors='raise') # Re-run with raise to ensure all or nothing
                except (ValueError, TypeError):
                    # If conversion fails for a column, leave it as is.
                    # This is expected, as not all object columns are dates.
                    pass
        
        df_store["df"] = df
        
        # Analyze columns on the (potentially) type-converted dataframe
        column_info = analyze_columns(df)
        return {"filename": file.filename, "columns": column_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

# The /suggest and /generate-chart endpoints remain the same as the previous "beautiful" version
# as they operate on the dataframe that has already been correctly processed.

@app.get("/suggest")
async def suggest_charts():
    """Analyzes the dataframe and suggests a wide range of relevant charts."""
    df = df_store.get("df")
    if df is None:
        raise HTTPException(status_code=404, detail="No data available. Please upload a CSV first.")

    column_info = analyze_columns(df)
    suggestions = []
    
    numeric_cols = [k for k, v in column_info.items() if v['type'] == 'numeric']
    date_cols = [k for k, v in column_info.items() if v['type'] == 'datetime']
    cat_low_cardinality = [k for k, v in column_info.items() if v['type'] == 'categorical' and v['cardinality'] == 'low']

    # Rule 1: Time Series (Line Chart) for each Date vs. each Numeric
    if date_cols and numeric_cols:
        for date_col in date_cols:
            for num_col in numeric_cols:
                suggestions.append({
                    "title": f"Trend of {num_col} over {date_col}",
                    "chart_type": "line", "x": date_col, "y": num_col
                })

    # Rule 2: Categorical Comparison (Bar Chart) for each low-cardinality Cat vs. each Numeric
    if cat_low_cardinality and numeric_cols:
        for cat_col in cat_low_cardinality:
            for num_col in numeric_cols:
                suggestions.append({
                    "title": f"Average {num_col} by {cat_col}",
                    "chart_type": "bar", "x": cat_col, "y": num_col, "aggregation": "mean"
                })

    # Rule 3: Correlation (Scatter Plot) for every pair of Numeric columns
    if len(numeric_cols) >= 2:
        for x_col, y_col in combinations(numeric_cols, 2):
            suggestions.append({
                "title": f"Correlation between {x_col} and {y_col}",
                "chart_type": "scatter", "x": x_col, "y": y_col
            })

    # Rule 4: Distribution (Histogram) for each Numeric column
    for num_col in numeric_cols:
        suggestions.append({
            "title": f"Distribution of {num_col}",
            "chart_type": "histogram", "x": num_col
        })
        
    # Rule 5: Distribution across categories (Box Plot)
    if cat_low_cardinality and numeric_cols:
        for cat_col in cat_low_cardinality:
            for num_col in numeric_cols:
                 suggestions.append({
                    "title": f"Distribution of {num_col} by {cat_col}",
                    "chart_type": "box", "x": cat_col, "y": num_col
                })

    # Rule 6: Proportions (Pie Chart) for each low-cardinality Categorical
    for cat_col in cat_low_cardinality:
        suggestions.append({
            "title": f"Proportions of {cat_col}",
            "chart_type": "pie", "names": cat_col
        })

    # Rule 7: Correlation Matrix (Heatmap) for all numeric columns
    if len(numeric_cols) > 1:
        suggestions.append({
            "title": "Numeric Correlation Heatmap",
            "chart_type": "heatmap"
        })
        
    return suggestions

@app.post("/generate-chart")
async def generate_chart(chart_config: dict):
    """Generates a Plotly chart based on a detailed configuration."""
    df = df_store.get("df")
    if df is None:
        raise HTTPException(status_code=404, detail="No data available.")

    try:
        chart_type = chart_config.get("chart_type")
        x_col = chart_config.get("x")
        y_col = chart_config.get("y")
        color_col = chart_config.get("color")
        agg = chart_config.get("aggregation")
        names_col = chart_config.get("names")
        
        fig = None
        title = chart_config.get("title", "Generated Chart")

        if chart_type == 'line':
            fig = px.line(df, x=x_col, y=y_col, color=color_col, title=title)
        elif chart_type == 'scatter':
            fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=title)
        elif chart_type == 'histogram':
            fig = px.histogram(df, x=x_col, color=color_col, title=title)
        elif chart_type == 'box':
             fig = px.box(df, x=x_col, y=y_col, color=color_col, title=title)
        elif chart_type == 'pie':
            fig = px.pie(df, names=names_col, title=title)
        elif chart_type == 'bar':
            if not agg: agg = 'sum'
            grouped_df = df.groupby(x_col, as_index=False).agg({y_col: agg})
            fig = px.bar(grouped_df, x=x_col, y=y_col, color=color_col, title=title)
        elif chart_type == 'heatmap':
            numeric_cols = df.select_dtypes(include='number').columns
            corr_matrix = df[numeric_cols].corr()
            fig = px.imshow(corr_matrix, text_auto=True, title=title, color_continuous_scale='RdBu_r')

        if fig is None:
            raise HTTPException(status_code=400, detail="Invalid chart configuration.")

        return JSONResponse(content=fig.to_json())

    except Exception as e:
        if isinstance(e, KeyError):
            raise HTTPException(status_code=400, detail=f"Chart generation failed. Column not found: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate chart: {e}")