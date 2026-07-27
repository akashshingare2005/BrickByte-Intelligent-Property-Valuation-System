import pandas as pd
import numpy as np
import joblib
import os
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import GradientBoostingRegressor, ExtraTreesRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# Configuration
# Dataset path adjusted based on project structure
DATASET_PATH = os.path.join('RealEststeAgent', 'static', 'house_price_dataset_india_12k.csv')
if not os.path.exists(DATASET_PATH):
    # Fallback if running from a different context
    DATASET_PATH = os.path.join('static', 'house_price_dataset_india_12k.csv')

def build_and_train():
    print(f"Loading dataset from: {DATASET_PATH}...")
    if not os.path.exists(DATASET_PATH):
        print(f"Error: Dataset not found at {DATASET_PATH}")
        return

    df = pd.read_csv(DATASET_PATH)

    # Define features and target
    target = 'Market_Price_INR'
    
    categorical_features = ['City', 'Locality_Tier', 'Furnishing']
    numerical_features = [
        'BHK', 'Bathrooms', 'Super_Area_sqft', 'Carpet_Area_sqft', 
        'Floor_No', 'Total_Floors', 'Property_Age_years', 'Parking', 
        'Lift', 'Gated_Society', 'Distance_to_Metro_km', 
        'Distance_to_CityCenter_km', 'Nearby_School_km', 
        'Nearby_Hospital_km', 'Crime_Rate_Index'
    ]

    X = df[categorical_features + numerical_features]
    y = df[target]

    # Preprocessing
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numerical_features),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
        ])

    # Define Candidate Models
    models = {
        "xgboost": XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6, random_state=42),
        "lightgbm": LGBMRegressor(n_estimators=500, learning_rate=0.05, num_leaves=31, random_state=42),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=300, learning_rate=0.1, max_depth=5, random_state=42),
        "extra_trees": ExtraTreesRegressor(n_estimators=300, max_depth=10, random_state=42)
    }

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Calculate City Average Prices for Investment Score
    print("Calculating city average prices for metadata...")
    city_avg_prices = df.groupby('City')['Price_per_sqft_INR'].mean().to_dict()

    print("\nTraining and Evaluating Models:")
    print("-" * 50)
    
    results = {}

    for name, model in models.items():
        print(f"Training Model: {name}...")
        
        # Create Pipeline
        pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('regressor', model)
        ])
        
        # Fit model
        pipeline.fit(X_train, y_train)
        
        # Evaluate
        y_pred = pipeline.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        # In regression, R2 is often used as a proxy for "Accuracy"
        accuracy = r2 * 100 
        
        print(f"  Accuracy (R² Score): {accuracy:.2f}%")
        print(f"  Mean Absolute Error: {mae:,.2f} INR")
        
        # Save model
        save_path = f'real_estate_{name}.pkl'
        print(f"  Saving model to {save_path}...")
        joblib.dump({
            'pipeline': pipeline,
            'city_avg_prices': city_avg_prices,
            'model_name': name,
            'accuracy': accuracy
        }, save_path)
        
        results[name] = accuracy
        print("-" * 50)

    print("\nSummary Comparison:")
    for name, acc in results.items():
        print(f"{name.upper():<20} | Accuracy (R² Score): {acc:.2f}%")

    print("\nModel creation complete! 4 separate .pkl files generated.")

if __name__ == "__main__":
    build_and_train()
