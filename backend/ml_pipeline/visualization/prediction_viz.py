"""
Prediction Visualization Tools
=============================

Generates interactive maps and static charts for model analysis.
"""

import folium
from folium.plugins import HeatMap
import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
import numpy as np
import base64
from io import BytesIO

class PredictionVisualizer:
    
    def create_probability_heatmap(self, predictions_gdf: gpd.GeoDataFrame, base_map='CartoDB dark_matter', threshold=0.3):
        """
        Create interactive Folium map with probability heatmap.
        Args:
            predictions_gdf: GeoDataFrame with 'latitude', 'longitude', 'probability'.
            threshold: Minimum probability to show in heatmap (reduces noise).
        """
        center_lat = predictions_gdf['latitude'].mean()
        center_lon = predictions_gdf['longitude'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles=base_map)
        
        # 1. Heatmap Layer
        # Filter low prob points to keep map clean
        heat_data = predictions_gdf[predictions_gdf['probability'] > threshold]
        heat_data = heat_data[['latitude', 'longitude', 'probability']].values.tolist()
        
        HeatMap(heat_data, radius=15, blur=10, max_zoom=1).add_to(m)
        
        # 2. High Risk Markers (Top 50)
        top_risks = predictions_gdf.nlargest(50, 'probability')
        for idx, row in top_risks.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=5,
                color='red',
                fill=True,
                popup=f"Prob: {row['probability']:.2f}"
            ).add_to(m)
            
        return m

    def plot_feature_importance(self, importances, top_n=20):
        """
        Horizontal bar chart of feature importances.
        """
        features, scores = zip(*importances[:top_n])
        
        plt.figure(figsize=(10, 8))
        sns.barplot(x=scores, y=features, palette='viridis')
        plt.title(f'Top {top_n} Predictors of Abandonment')
        plt.xlabel('Importance Score')
        plt.tight_layout()
        
        # Return as image bytes usually, or just fig
        return plt.gcf()
        
    def create_prediction_comparison(self, rf_pred, spatial_pred, kde_pred, ensemble_pred, shape):
        """
        4-panel plot comparing the different model views.
        """
        fig, axes = plt.subplots(2, 2, figsize=(15, 15))
        
        # Reshape 1D arrays to Grid 2D
        rf_grid = rf_pred.reshape(shape)
        sp_grid = spatial_pred.reshape(shape)
        kde_grid = kde_pred.reshape(shape)
        ens_grid = ensemble_pred.reshape(shape)
        
        sns.heatmap(rf_grid, ax=axes[0,0], cmap='Reds', cbar=False).set_title('Random Forest (Feature Only)')
        axes[0,0].axis('off')
        
        sns.heatmap(sp_grid, ax=axes[0,1], cmap='Blues', cbar=False).set_title('DBSCAN (Clusters)')
        axes[0,1].axis('off')
        
        sns.heatmap(kde_grid, ax=axes[1,0], cmap='Greens', cbar=False).set_title('KDE (Density)')
        axes[1,0].axis('off')
        
        sns.heatmap(ens_grid, ax=axes[1,1], cmap='inferno', cbar=True).set_title('ENSEMBLE (Combined)')
        axes[1,1].axis('off')
        
        plt.tight_layout()
        return fig
