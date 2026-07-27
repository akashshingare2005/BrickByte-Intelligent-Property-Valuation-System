import pandas as pd
import numpy as np
import joblib
import os
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# Configuration
DATASET_PATH = os.path.join('RealEststeAgent', 'static', 'house_price_dataset_india_12k.csv')
if not os.path.exists(DATASET_PATH):
    DATASET_PATH = os.path.join('static', 'house_price_dataset_india_12k.csv')
MODEL_SAVE_PATH = 'real_estate_extra_trees.pkl'

def train_extra_trees():
    print(f"Loading dataset from: {DATASET_PATH}...")
    if not os.path.exists(DATASET_PATH):
        print(f"Error: Dataset not found at {DATASET_PATH}")
        return

    df = pd.read_csv(DATASET_PATH)

    # Features and Target
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

    # Model Pipeline
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', ExtraTreesRegressor(n_estimators=300, max_depth=10, random_state=42))
    ])

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train
    print("Training Extra Trees Regressor...")
    model_pipeline.fit(X_train, y_train)

    # Evaluate
    y_pred = model_pipeline.predict(X_test)
    accuracy = r2_score(y_test, y_pred) * 100
    mae = mean_absolute_error(y_test, y_pred)
    
    print(f"Accuracy (R² Score): {accuracy:.2f}%")
    print(f"Mean Absolute Error: {mae:,.2f} INR")

    # Metadata
    city_avg_prices = df.groupby('City')['Price_per_sqft_INR'].mean().to_dict()

    # Save
    print(f"Saving model to {MODEL_SAVE_PATH}...")
    joblib.dump({
        'pipeline': model_pipeline,
        'city_avg_prices': city_avg_prices,
        'model_name': 'extra_trees',
        'accuracy': accuracy
    }, MODEL_SAVE_PATH)

    print("Success: Extra Trees pipeline complete!")

if __name__ == "__main__":
    train_extra_trees()
