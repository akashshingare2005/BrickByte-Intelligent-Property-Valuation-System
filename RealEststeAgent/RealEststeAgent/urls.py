from django.contrib import admin
from django.urls import path
from customapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('emi-calculator/', views.emi_calculator, name='emi_calculator'),
    path('market-trends/', views.market_trends, name='market_trends'),
    path('compare-properties/', views.compare_properties, name='compare_properties'),
    path('prediction-history/', views.prediction_history, name='prediction_history'),
    path('download-report/', views.download_report, name='download_report'),
    path('predict/', views.predict_house_price, name='predict'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password, name='reset_password'),
    path('about-project/', views.about_project, name='about_project'),
    path('investment-insights/', views.investment_insights, name='investment_insights'),
    path('location-analytics/', views.location_analytics, name='location_analytics'),
    path('api/location-analytics-data/', views.location_analytics_data, name='location_analytics_data'),
    path('account/', views.account, name='account'),
    path('contact/', views.contact, name='contact'),
    path('job-list/', views.job_list, name='job_list'),
    path('testimonial/', views.testimonial, name='testimonial'),
]
