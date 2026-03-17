from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
import os
import joblib
import pandas as pd

User = get_user_model()
def index(request):
    return render(request, 'index.html')

def emi_calculator(request):
    return render(request, 'EMI_Calculator.html')

def market_trends(request):
    plots_dir = os.path.join(settings.BASE_DIR, 'RealEststeAgent', 'static', 'plots', 'market_trends')
    plot_images = []
    if os.path.exists(plots_dir):
        for f in os.listdir(plots_dir):
            if f.endswith('.png'):
                # Extract clean title: "BHK_by_city.png" -> "Bhk By City" -> Drop "_by_city.png" -> "Bhk"
                title_str = f.replace('_by_city.png', '').replace('_', ' ').title()
                plot_images.append({'filename': f, 'title': title_str})
    return render(request, 'Market_Trends.html', {'plot_images': plot_images})

from django.core.paginator import Paginator

def compare_properties(request):
    # Load dataset
    csv_path = os.path.join(settings.BASE_DIR, 'RealEststeAgent', 'static', 'house_price_dataset_india_12k.csv')
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        messages.error(request, f"Could not load property data: {e}")
        return render(request, 'Compare_Properties.html', {'properties': []})

    # Get filter parameters
    city = request.GET.get('city')
    bhk = request.GET.get('bhk')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort_by')

    # Apply filters
    if city:
        df = df[df['City'].str.lower() == city.lower()]
    if bhk and bhk.isdigit():
        df = df[df['BHK'] == int(bhk)]
    if min_price and min_price.isdigit():
        df = df[df['Market_Price_INR'] >= int(min_price)]
    if max_price and max_price.isdigit():
        df = df[df['Market_Price_INR'] <= int(max_price)]

    # Apply sorting
    if sort_by == 'price_asc':
        df = df.sort_values(by='Market_Price_INR', ascending=True)
    elif sort_by == 'price_desc':
        df = df.sort_values(by='Market_Price_INR', ascending=False)
    elif sort_by == 'area_desc':
        df = df.sort_values(by='Super_Area_sqft', ascending=False)
    else:
        # Default sort
        df = df.sort_values(by='House_ID', ascending=True)

    # Convert to dictionary records
    properties_list = df.to_dict('records')

    # Pagination: 40 properties per page
    paginator = Paginator(properties_list, 40)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get unique cities for the filter dropdown
    try:
        cities = sorted(pd.read_csv(csv_path)['City'].unique().tolist())
    except:
        cities = []

    context = {
        'page_obj': page_obj,
        'cities': cities,
        'current_filters': {
            'city': city or '',
            'bhk': bhk or '',
            'min_price': min_price or '',
            'max_price': max_price or '',
            'sort_by': sort_by or '',
        }
    }

    return render(request, 'Compare_Properties.html', context)

def prediction_history(request):
    return render(request, 'Prediction_History.html')

def download_report(request):
    return render(request, 'Download_Report.html')

def login(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'signup':
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists")
                return redirect('login')
                
            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already registered")
                return redirect('login')
                
            user = User.objects.create_user(username=username, email=email, password=password)
            user.is_verified = False
            user.save()
            
            # Send verification email
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verify_url = request.build_absolute_uri(reverse('verify_email', kwargs={'uidb64': uid, 'token': token}))
            
            send_mail(
                'Verify your Email',
                f'Please click the link below to verify your email:\n\n{verify_url}',
                settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') else 'noreply@realestate.com',
                [user.email],
                fail_silently=False,
            )
            
            messages.success(request, "Account created! Please check your email to verify your account.")
            return redirect('login')
            
        elif action == 'login':
            username = request.POST.get('username')
            password = request.POST.get('password')
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if not user.is_verified:
                    messages.error(request, "Please verify your email before logging in")
                    return redirect('login')
                    
                auth_login(request, user)
                return redirect('account')
            else:
                messages.error(request, "Invalid username or password")
                return redirect('login')
                
    return render(request, 'Login_Signup.html')

def logout_view(request):
    auth_logout(request)
    return redirect('login')

def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_verified = True
        user.save()
        messages.success(request, 'Email verified successfully! You can now log in.')
    else:
        messages.error(request, 'Verification link is invalid or has expired.')
        
    return redirect('login')

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = request.build_absolute_uri(reverse('reset_password', kwargs={'uidb64': uid, 'token': token}))
            
            send_mail(
                'Password Reset Request',
                f'Click the link to reset your password:\n\n{reset_url}',
                settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') else 'noreply@realestate.com',
                [user.email],
                fail_silently=False,
            )
            messages.success(request, "A password reset link has been sent to your email.")
            return redirect('login')
        except User.DoesNotExist:
            # For security, you might just want to show "Email sent" here too
            messages.error(request, "No account found with this email.")
            return redirect('forgot_password')
            
    return render(request, 'forgot_password.html')

def reset_password(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password = request.POST.get('password')
            user.set_password(new_password)
            user.save()
            messages.success(request, "Your password has been reset successfully. Please log in.")
            return redirect('login')
        return render(request, 'reset_password.html')
    else:
        messages.error(request, 'Password reset link is invalid or has expired.')
        return redirect('login')

def about_project(request):
    return render(request, 'About_Project.html')

@login_required(login_url='login')
def account(request):
    return render(request, 'account.html')

def investment_insights(request):
    return render(request, 'Investment_Insights.html')

from django.http import JsonResponse

def location_analytics(request):
    return render(request, 'Location_Analytics.html')

def location_analytics_data(request):
    csv_path = os.path.join(settings.BASE_DIR, 'RealEststeAgent', 'static', 'house_price_dataset_india_12k.csv')
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        

    # Aggregate data by city
    # Avoid calculating on empty dataframe
    if df.empty:
        return JsonResponse({'cities_data': [], 'scatter_data': []})

    # Prepare scatter plot data (taking a sample if too large)
    scatter_sample = df[['Distance_to_CityCenter_km', 'Market_Price_INR']].dropna()
    if len(scatter_sample) > 500:
        scatter_sample = scatter_sample.sample(500)
    scatter_data = [{'x': row['Distance_to_CityCenter_km'], 'y': row['Market_Price_INR']} for _, row in scatter_sample.iterrows()]

    agg_funcs = {
        'House_ID': 'count',
        'Market_Price_INR': 'mean',
        'Price_per_sqft_INR': 'mean',
        'BHK': 'mean',
        'Property_Age_years': 'mean',
        'Crime_Rate_Index': 'mean',
        'Distance_to_CityCenter_km': 'mean'
    }
    
    grouped = df.groupby('City').agg(agg_funcs).reset_index()
    
    # Static coordinates for primary cities
    city_coords = {
        'Bangalore': [12.9716, 77.5946],
        'Hyderabad': [17.3850, 78.4867],
        'Mumbai': [19.0760, 72.8777],
        'Nagpur': [21.1458, 79.0882],
        'Pune': [18.5204, 73.8567]
    }
    
    cities_data = []
    for _, row in grouped.iterrows():
        c_name = row['City']
        count = row['House_ID']
        avg_price = row['Market_Price_INR']
        avg_sqft = row['Price_per_sqft_INR']
        avg_bhk = row['BHK']
        avg_age = row['Property_Age_years']
        crime_rate = row['Crime_Rate_Index']
        city_center_dist = row['Distance_to_CityCenter_km']
        
        coords = city_coords.get(c_name, [20.5937, 78.9629]) # Fallback center India
        
        cities_data.append({
            'city': c_name,
            'count': int(count),
            'avg_price': float(avg_price),
            'avg_price_sqft': float(avg_sqft),
            'avg_bhk': float(avg_bhk),
            'avg_age': float(avg_age),
            'crime_rate': float(crime_rate),
            'city_center_dist': float(city_center_dist),
            'lat': coords[0],
            'lng': coords[1]
        })

    return JsonResponse({
        'cities_data': cities_data,
        'scatter_data': scatter_data
    })

def contact(request):
    return render(request, 'contact.html')

def job_list(request):
    return render(request, 'job-list.html')

def testimonial(request):
    return render(request, 'testimonial.html')


def predict_house_price(request):
    if request.method == 'POST':
        # Load the saved ML model & Pipeline
        try:
            model_path = os.path.join(settings.BASE_DIR, 'real_estate_model.pkl')
            saved_data = joblib.load(model_path)
            model_pipeline = saved_data['pipeline']
            city_avg_price_sqft = saved_data['city_avg_prices']
            
            # Extract form inputs 
            user_input = {
                'City': request.POST.get('city'),
                'Locality_Tier': request.POST.get('locality_tier'),
                'BHK': int(request.POST.get('bhk', 0)),
                'Bathrooms': int(request.POST.get('bathrooms', 0)),
                'Super_Area_sqft': float(request.POST.get('super_area', 0.0)),
                'Carpet_Area_sqft': float(request.POST.get('carpet_area', 0.0)),
                'Floor_No': 3,  # Baseline assumption if missing
                'Total_Floors': 5, # Baseline assumption if missing
                'Property_Age_years': int(request.POST.get('property_age', 0)),
                'Distance_to_Metro_km': float(request.POST.get('metro_dist', 0.0)),
                'Distance_to_CityCenter_km': float(request.POST.get('city_center_dist', 0.0)),
                'Nearby_School_km': 1.0,    # Baseline assumption if missing
                'Nearby_Hospital_km': 2.0,  # Baseline assumption if missing
                'Crime_Rate_Index': 25.0,   # Baseline assumption if missing
                'Parking': int(request.POST.get('parking', 0)),
                'Furnishing': request.POST.get('furnishing'),
                'Lift': int(request.POST.get('lift', 0)),
                'Gated_Society': int(request.POST.get('gated', 0))
            }

            # Create DataFrame
            input_df = pd.DataFrame([user_input])
            
            # Inference!
            predicted_price = model_pipeline.predict(input_df)[0]
            
            # Investment Score Logic
            city = user_input['City']
            area = user_input['Super_Area_sqft']
            predicted_price_sqft = predicted_price / area if area > 0 else 0
            market_avg_sqft = city_avg_price_sqft.get(city, 0)
            
            if market_avg_sqft == 0:
                inv_score = "Unknown (City average data missing)"
            else:
                diff_pct = ((predicted_price_sqft - market_avg_sqft) / market_avg_sqft) * 100
                if diff_pct < -10:
                    inv_score = "Good Investment (Below Market Avg)"
                elif diff_pct > 10:
                    inv_score = "Overpriced (Above Market Avg)"
                else:
                    inv_score = "Average (At Market Price)"

            # Format outputs
            formatted_price = f"₹ {predicted_price:,.2f}"
            
            return render(request, 'predict.html', {
                'price': formatted_price, 
                'score': inv_score
            })
            
        except Exception as e:
            return render(request, 'predict.html', {'error': f"Prediction Error: {str(e)}"})
            
    # GET request handler
    return render(request, 'predict.html')
