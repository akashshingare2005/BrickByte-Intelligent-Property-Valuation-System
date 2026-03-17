import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import joblib
import os

# Set plotting style
plt.style.use('ggplot')
sns.set_theme(style="whitegrid")

def load_and_preprocess_data(csv_path):
    print("1. Loading dataset...")
    df = pd.read_csv(csv_path)

    print("2. Performing Data Cleaning...")
    # Handle missing values by dropping them (assuming minimal missing data for this dataset)
    df = df.dropna()

    # Drop columns that are completely irrelevant or cause data leakage
    if 'House_ID' in df.columns:
        df = df.drop('House_ID', axis=1)
    
    # CRITICAL: We MUST drop Price_per_sqft_INR to prevent data leakage. 
    # If the model knows price/sqft, it just multiplies by area to get exact Market Price.
    if 'Price_per_sqft_INR' in df.columns:
        # We will save the average price per sqft per city for the Investment Score Logic later
        city_avg_price_sqft = df.groupby('City')['Price_per_sqft_INR'].mean().to_dict()
        df = df.drop('Price_per_sqft_INR', axis=1)
    else:
        city_avg_price_sqft = {}

    print("3. Feature Engineering & Splitting Data...")
    X = df.drop('Market_Price_INR', axis=1)
    y = df['Market_Price_INR']

    # Define features by type for the pipeline
    categorical_features_onehot = ['City']
    categorical_features_ordinal = ['Locality_Tier', 'Furnishing']
    numerical_features = ['BHK', 'Bathrooms', 'Super_Area_sqft', 'Carpet_Area_sqft', 
                          'Floor_No', 'Total_Floors', 'Property_Age_years', 
                          'Distance_to_Metro_km', 'Distance_to_CityCenter_km', 
                          'Nearby_School_km', 'Nearby_Hospital_km', 'Crime_Rate_Index']

    # Construct the preprocessing steps
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numerical_features),
            ('cat_onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features_onehot),
            ('cat_ordinal', OrdinalEncoder(categories=[
                ['Budget', 'Mid', 'Premium'], 
                ['Unfurnished', 'Semi-Furnished', 'Fully-Furnished']
            ], handle_unknown='use_encoded_value', unknown_value=-1), categorical_features_ordinal)
        ],
        remainder='passthrough' # For Parking, Lift, Gated_Society
    )

    # 4. Split dataset into training and testing sets (80/20)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    return X_train, X_test, y_train, y_test, preprocessor, city_avg_price_sqft, df

def train_and_evaluate_models(X_train, X_test, y_train, y_test, preprocessor):
    print("\n5. Training Regression Models...")
    
    models = {
        'Linear Regression': LinearRegression(),
        'Random Forest Regressor': RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1),
        'XGBoost Regressor': xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=7, random_state=42, n_jobs=-1)
    }

    best_model = None
    best_r2_score = -float('inf')
    best_model_name = ""
    best_pipeline = None

    print("\n6. Evaluating Models...")
    for name, model in models.items():
        # Create pipeline for each model to ensure exact same preprocessing
        pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('model', model)
        ])
        
        # Train
        pipeline.fit(X_train, y_train)
        
        # Predict on Test Set
        y_pred = pipeline.predict(X_test)
        
        # Evaluate
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        
        print(f"--- {name} ---")
        print(f"R² Score : {r2:.4f}")
        print(f"MAE      : INR {mae:,.2f}")
        print(f"MSE      : {mse:,.2f}")
        
        # Keep track of the best model based on R2 Score
        if r2 > best_r2_score:
            best_r2_score = r2
            best_model_name = name
            best_model = model
            best_pipeline = pipeline

    print(f"\n7. Best Model Selected: {best_model_name} with R² Score of {best_r2_score:.4f}")
    return best_pipeline, best_model_name

def plot_visualizations(best_pipeline, X_train, X_test, y_test, df):
    print("\nGenerating Visualizations...")
    os.makedirs('static/plots', exist_ok=True)
    
    # --- A. Correlation Heatmap ---
    plt.figure(figsize=(14, 10))
    # Select only numeric columns for correlation matrix
    numeric_df = df.select_dtypes(include=[np.number])
    corr_matrix = numeric_df.corr()
    
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm", cbar=True, square=True, 
                annot_kws={'size': 8})
    plt.title('Feature Correlation Heatmap', fontsize=16)
    plt.tight_layout()
    plt.savefig('static/plots/correlation_heatmap.png')
    plt.close()
    print("Saved Correlation Heatmap: static/plots/correlation_heatmap.png")

    # --- B. Predicted vs Actual Prices Plot ---
    y_pred_best = best_pipeline.predict(X_test)
    
    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred_best, alpha=0.5, color='blue', edgecolor='k')
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2) # Diagonal line
    plt.xlabel('Actual Prices (INR)', fontsize=12)
    plt.ylabel('Predicted Prices (INR)', fontsize=12)
    plt.title('Actual vs Predicted House Prices', fontsize=14)
    plt.tight_layout()
    plt.savefig('static/plots/actual_vs_predicted.png')
    plt.close()
    print("Saved Actual vs Predicted Plot: static/plots/actual_vs_predicted.png")
    
    # --- C. Feature Importance ---
    # Attempt to extract feature importance if the model supports it
    model = best_pipeline.named_steps['model']
    preprocessor = best_pipeline.named_steps['preprocessor']
    
    if hasattr(model, 'feature_importances_'):
        # Get feature names after transformation
        feature_names = []
        
        # Numeric names stay the same
        num_features = preprocessor.transformers_[0][2]
        feature_names.extend(num_features)
        
        # OneHot names
        ohe = preprocessor.transformers_[1][1]
        ohe_features = ohe.get_feature_names_out(preprocessor.transformers_[1][2])
        feature_names.extend(ohe_features)
        
        # Ordinal names
        ord_features = preprocessor.transformers_[2][2]
        feature_names.extend(ord_features)
        
        # Remainder (boolean/binary columns passthrough)
        # Hack to get remainder feature names dynamically
        # Since remainder=passthrough, the remaining columns are added at the end.
        all_cols_before = set(num_features).union(set(preprocessor.transformers_[1][2])).union(set(ord_features))
        remainder_cols = [c for c in X_train.columns if c not in all_cols_before]
        feature_names.extend(remainder_cols)

        # Zip importances
        importance = model.feature_importances_
        
        # Ensure lengths match in case scikit-learn handles it slightly differently internally
        if len(feature_names) == len(importance):
            feat_imp_df = pd.DataFrame({'Feature': feature_names, 'Importance': importance})
            feat_imp_df = feat_imp_df.sort_values('Importance', ascending=False).head(15) # Top 15
            
            plt.figure(figsize=(12, 8))
            sns.barplot(x='Importance', y='Feature', data=feat_imp_df, palette='viridis')
            plt.title('Top 15 Feature Importances', fontsize=14)
            plt.xlabel('Relative Importance')
            plt.tight_layout()
            plt.savefig('static/plots/feature_importance.png')
            plt.close()
            print("Saved Feature Importance Plot: static/plots/feature_importance.png")

def predict_property(model_pipeline, city_avg_price_sqft, input_data):
    """
    Prediction function taking user input dictionary and returning price & investment score.
    """
    print("\n--- Running Prediction Simulation ---")
    
    # Convert input to DataFrame strictly matching training data format
    input_df = pd.DataFrame([input_data])
    
    # Expected Default columns if user drops any
    expected_cols = ['City', 'Locality_Tier', 'BHK', 'Bathrooms', 'Super_Area_sqft', 
                     'Carpet_Area_sqft', 'Floor_No', 'Total_Floors', 'Property_Age_years', 
                     'Parking', 'Furnishing', 'Lift', 'Gated_Society', 'Distance_to_Metro_km', 
                     'Distance_to_CityCenter_km', 'Nearby_School_km', 'Nearby_Hospital_km', 'Crime_Rate_Index']
    
    # Ensure all expected columns exist (fill missing with median/mode standard assumptions)
    for col in expected_cols:
        if col not in input_df.columns:
            if col in ['City', 'Locality_Tier', 'Furnishing']:
                input_df[col] = 'Unknown'
            else:
                input_df[col] = 0
    
    predicted_price = model_pipeline.predict(input_df)[0]
    
    # Calculate Investment Score
    city = input_data.get('City', 'Unknown')
    area = float(input_data.get('Super_Area_sqft', 1))
    
    predicted_price_sqft = predicted_price / area if area > 0 else 0
    market_avg_sqft = city_avg_price_sqft.get(city, 0)
    
    if market_avg_sqft == 0:
        inv_score = "Unknown (City average data missing)"
    else:
        # If predicted price per sqft is > 10% lower than market average -> Good
        # If predicted price per sqft is > 10% higher than market average -> Overpriced
        # Else -> Average
        diff_pct = ((predicted_price_sqft - market_avg_sqft) / market_avg_sqft) * 100
        
        if diff_pct < -10:
            inv_score = "Good Investment (Below Market Avg)"
        elif diff_pct > 10:
            inv_score = "Overpriced (Above Market Avg)"
        else:
            inv_score = "Average (At Market Price)"
            
    return predicted_price, inv_score


def main():
    # Setup paths
    # Because script is in RealEststeAgent/, we need to go into RealEststeAgent/static/ 
    csv_path = os.path.join(os.path.dirname(__file__), 'RealEststeAgent', 'static', 'house_price_dataset_india_12k.csv')
    
    # 1 to 4 limit: Preprocess
    X_train, X_test, y_train, y_test, preprocessor, city_avg_price_sqft, df = load_and_preprocess_data(csv_path)
    
    # 5 & 6 & 7: Train & Evaluate
    best_pipeline, best_model_name = train_and_evaluate_models(X_train, X_test, y_train, y_test, preprocessor)
    
    # Plotting
    plot_visualizations(best_pipeline, X_train, X_test, y_test, df)
    
    # 8. Save the Model
    print("\n8. Saving Model...")
    joblib.dump({'pipeline': best_pipeline, 'city_avg_prices': city_avg_price_sqft}, 'real_estate_model.pkl')
    print("Model successfully saved as 'real_estate_model.pkl'!")
    
    # Prediction System Simulation
    user_input = {
        'City': 'Pune',
        'Locality_Tier': 'Mid',            # Assumption based on 1200 sqft / 2 BHK
        'BHK': 2,
        'Bathrooms': 2,                    # Standard assumption
        'Super_Area_sqft': 1200,
        'Carpet_Area_sqft': 950,           # Standard assumption for Carpet Area
        'Floor_No': 3,
        'Total_Floors': 7,
        'Property_Age_years': 5,
        'Distance_to_Metro_km': 2,
        'Parking': 1,                      # 1 for Yes
        'Lift': 1,                         # 1 for Yes
        'Gated_Society': 1,
        'Furnishing': 'Semi-Furnished',    # Standard assumption
        'Distance_to_CityCenter_km': 8,
        'Nearby_School_km': 1,
        'Nearby_Hospital_km': 2,
        'Crime_Rate_Index': 25.0
    }
    
    price, score = predict_property(best_pipeline, city_avg_price_sqft, user_input)
    
    print(f"\nExample Prediction Input:\n{user_input}")
    print(f"\n=> Predicted Price (INR): INR {price:,.2f}")
    print(f"=> Investment Score: {score}\n")
    print("ML Pipeline execution completed successfully.")

if __name__ == "__main__":
    main()
