from flask import Flask, render_template, request, redirect, url_for,session,jsonify
from geopy.geocoders import Nominatim
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import folium
from flask_cors import CORS
from flask_pymongo import PyMongo
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
from pymongo import MongoClient
from web3 import Web3
from web3.middleware import geth_poa_middleware
sns.set()

app = Flask(__name__)
CORS(app)

app.config['MONGO_DBNAME'] = 'FarmEz'
app.config['MONGO_URI'] = 'mongodb+srv://nareshvaishnavrko11:nareshrko11@cluster0.hudqzdr.mongodb.net/FarmEz'
client = MongoClient('mongodb+srv://nareshvaishnavrko11:nareshrko11@cluster0.hudqzdr.mongodb.net/')

db = client['FarmEz']
shopping_list_collection = db['cart']
users_collection = db['users']
mongo = PyMongo(app)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = 'nareshrko10'
app.config['SESSION_COOKIE_SECURE'] = True  # Ensures session cookie is sent only over HTTPS (secure)
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevents access to the session cookie via JavaScript
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Session cookie sent with same-site requests (Lax or Strict)

raw_data = pd.read_csv('FinalDataset2.csv')
raw_data = raw_data.drop(['Latitude', 'Longitude'], axis=1)

@app.route('/')
def index():
    return render_template('index.html')
    
@app.route('/about')
def about():
    return render_template('aboutus.html')

@app.route('/signin')
def signin():
    return render_template('signin.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/popup')
def popup():
    return render_template('popup.html')

@app.route('/signup')
def signup():
    return render_template('sign_up.html')

@app.route('/crop')
def home():
    return render_template('cindex.html')


@app.route('/chart', methods=['POST'])
def chart():
    
    raw_data['DISTRICT_NAME'] = raw_data['DISTRICT_NAME'].str.replace(' ', '')
    district = request.form['district']
    df = raw_data[raw_data['DISTRICT_NAME'] == district]
    
    df_sum = df.append(df.sum(numeric_only=True), ignore_index=True)
    sum_row = df_sum.iloc[[-1]]
    n_row = sum_row.drop('DISTRICT_NAME', axis=1)
    p_row = n_row.drop('TALUKA_NAME', axis=1)
    q_row = p_row.astype(int)
    max_row = q_row.loc[q_row.sum(axis=1).idxmax()]
    max_col = max_row.idxmax()
    row_to_analyze = q_row.iloc[0]
    top_5 = row_to_analyze.nlargest(5).index.tolist()
    
    crop1 = request.form['crop1']
    crop2 = request.form['crop2']
    crop3 = request.form['crop3']
    crop4 = request.form['crop4']
    crop5 = request.form['crop5']

    selected_crops = [crop1, crop2, crop3, crop4, crop5]
    lat_df = sum_row[selected_crops]

    fig, (ax1, ax2) = plt.subplots(ncols=2, figsize=(20, 10))
    plt.figure(figsize=(8, 6))
    sns.set_style('whitegrid')
    palette = 'Paired'
    ax = sns.barplot(data=lat_df, palette=palette)
    ax.tick_params(labelsize=12)
    ax.set_xlabel('Crops', fontsize=14)
    ax.set_ylabel('Yield', fontsize=14)
    ax.set_title('Crop Yield by Crop Type', fontsize=18)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig('static/chart1.png')

    colors = sns.color_palette('Paired')
    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(lat_df.values[0], colors=colors, autopct='%1.1f%%', shadow=False, startangle=90, 
                                    wedgeprops=dict(width=0.6, edgecolor='w'))
    ax.set_title('Pie Chart', fontsize=15)
    ax.legend(wedges, lat_df.columns, title='Crops', loc='center left', bbox_to_anchor=(1, 0, 0.5, 1))
    plt.tight_layout()
    plt.savefig('static/chart2.png', bbox_inches='tight')

    # selected_crops = [crop1, crop2, crop3, crop4, crop5]
    top_districts = []
    for i in selected_crops:
        crop_data = raw_data[['DISTRICT_NAME'] + [i]]
        crop_data = crop_data.groupby('DISTRICT_NAME').sum().reset_index()
        crop_data['Total'] = crop_data[[i]].sum(axis=1)
        crop_data = crop_data.sort_values('Total', ascending=False).reset_index(drop=True)
        top_3 = crop_data.head(3)['DISTRICT_NAME'].tolist()
        top_districts.append((i, top_3))
    
    crops = []
    for crop in selected_crops:
        if lat_df[crop].iloc[0] == 0:
            crops.append((crop, f'does not grow in {district}.'))
        else:
            crops.append((crop, f'grows in {district}.'))

    return render_template('cindex.html', crops=crops, max_crop=max_col, top_5=top_5, top_districts=top_districts)

@app.route('/account', methods=['POST'])
def create_account():
    if request.method == 'POST':
        # Get form data
        full_name = request.form['full-name']
        age = request.form['age']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        phone = request.form['phone']
        district = request.form['district']
        taluka = request.form['taluka']

        # Check if the email already exists in the database
        existing_user = users_collection.find_one({"email": email})

        if existing_user:
            return jsonify({"error": "Email already registered. Please use a different email"})

        if password == confirm_password:
            # Check if a file was uploaded
            if 'Photo' in request.files:
                photo = request.files['Photo']
                if photo.filename != '':
                    # Securely save the uploaded photos to the defined folder
                    filename = secure_filename(photo.filename)
                    photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                else:
                    # Set filename to None if no photo is uploaded
                    filename = None
            else:
                # Set filename to None if no 'Photo' field in the request
                filename = None

            # Insert data into MongoDB, including the photo filename
            user_data = {
                'full-name': full_name,
                'age': age,
                'email': email,
                'password': password,
                'confirm_password': confirm_password,
                'phone': phone,
                'district': district,
                'taluka': taluka,
                'Photo': filename,
            }
            users_collection.insert_one(user_data)

            # Redirect to success page...
            return redirect(url_for('index'))
        else:
            return jsonify({"error": "Passwords do not match. Please try again"})
    else:
        return jsonify({"error": "Error"})


@app.route('/farmer')
def farmindex():
    return render_template('findex.html')


# Handle form submissions
@app.route('/Register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
    
        email = request.form['email']
        landsize = request.form['landsize']
        address = request.form['address']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        otherinfo = request.form['other-info']

        # Check if a file was uploaded
        if 'land_photo' in request.files:
            # photo = request.files['photo']
            land_photo = request.files['land_photo']
            land_photo_filename = secure_filename(land_photo.filename)
            
            # photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            land_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], land_photo_filename))
        else:
            land_photo_filename = None  # Or provide a default image path
        
        # Insert data into MongoDB
        
        mongo.db.users.update_one(
            {'email': email},
            {
                '$set': {
                    'landsize': landsize,
                    'address': address,
                    'latitude': latitude,
                    'longitude': longitude,
                    'other-info': otherinfo,
                    'land_photo': land_photo_filename
                }
            }
        ) 
        
        return redirect(url_for('popup'))
    else:
        return 'Error'
    

@app.route('/map', methods=['GET', 'POST'])
def display_map():

    if request.method == 'POST':
        district = request.form['district'].strip()

        # Query the MongoDB database for the latitude and longitude of the given district
        # and store the results in a list of dictionaries
        locations = list(mongo.db.users.find({'district': district, 'latitude': {'$exists': True}, 'longitude': {'$exists': True}}, {'_id': 0, 'latitude': 1, 'longitude': 1}))
        
        if not locations:
            return render_template('mindex.html', district=district, error='No records found for this district.')
        
        # Create a Folium map centered on the first location in the list
        map = folium.Map(location=[locations[0]['latitude'], locations[0]['longitude']], zoom_start=10)
        
        # Add markers for all the locations in the list
        for location in locations:
            # Query the MongoDB database for the user information
            user_info = mongo.db.users.find_one({'district': district, 'latitude': location['latitude'], 'longitude': location['longitude']})
            
            # Create the URL for the farmer's profile using the farmer's ID
            profile_url = url_for('farmer_profile', farmer_id = str(user_info['_id']))
            
            # Modify the popup HTML to include the "More Info" link leading to the farmer's profile
            popup_html = f"""
            <div style="width: 300px;">
                <h3 style="margin: 0; padding: 10px; background-color: #00704A; color: #FFF; text-align: center; font-size: 20px;">
                    {user_info['full-name']}
                </h3>
                <div style="padding: 10px;">
                    <p style="margin: 0; margin-bottom: 5px; font-size: 16px;">Phone: {user_info['phone']}</p>
                    <p style="margin: 0; margin-bottom: 5px; font-size: 16px;">Land Size: {user_info['landsize']} acres</p>
                    <div style="text-align: center;">
                        <a href='{profile_url}' target='_blank' style="color: #002F6C; text-decoration: none; font-size: 13px; display: inline-block;">More Info</a>
                    </div>
                </div>
            </div>
            """  # Add a marker with the pop-up to the map
            folium.Marker(location=[location['latitude'], location['longitude']], popup=popup_html).add_to(map)
        
        # Convert the map to HTML and pass it to the template
        map_html = map._repr_html_()
        return render_template('mindex.html', district=district, map_html=map_html)

    # If the request method is not 'POST', return the default map page
    return render_template('mindex.html', district='', map_html='', error='')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get email and password from the form
        email = request.form['email']
        password = request.form['password']

        # Check if the email exists in the database
        farmer_info = users_collection.find_one({'email': email})

        if farmer_info:
            # If the email and password match, store the user ID in the session
            if password == farmer_info['password']:
                session['farmer_id'] = str(farmer_info['_id'])
                return jsonify({"message": "Login successful"})
            else:
                # If the password doesn't match, show an error message
                return jsonify({"error": "Incorrect password. Please try again."})
        else:
            return jsonify({"error": "Incorrect email or password"})

    # If the request method is GET, render the login page (signin.html)
    return render_template('signin.html')


    
    
@app.route('/farmer/<farmer_id>')
def farmer_profile(farmer_id):
    # Check if the user is logged in by verifying the 'farmer_id' in the session
    logged_in_farmer_id = session.get('farmer_id')

    # Fetch the farmer's details from MongoDB using the given ID
    farmer_info = mongo.db.users.find_one({'_id': ObjectId(farmer_id)})

    if farmer_info:
        # If the user is logged in, allow them to view any farmer profile
        if logged_in_farmer_id:
            return render_template('profile.html', farmer_info=farmer_info)
        else:
            return "Access denied ! Log in first"
    else:
        return "Farmer not found"

        
# @app.route('/me/<farmer_id>')
# def my_profile(farmer_id):
#     # Check if the user is logged in by verifying the 'farmer_id' in the session
#     if 'farmer_id' in session and str(session['farmer_id']) == farmer_id:
#         # Fetch the farmer's details from MongoDB using the given ID
#         new_farmer_info = mongo.db.users.find_one({'_id': ObjectId(farmer_id)})
#          # Query trade IDs associated with the farmer's ID
#         trade = new_farmer_info['trade']['sell']
        
#         # Query trade data from the "trades" collection using the trade IDs
#         trade_listings = mongo.db.trades.find({'_id': {'$in': trade}})
#         if new_farmer_info:
#             return render_template('my_profile.html', new_farmer_info=new_farmer_info, trade_listings=trade_listings)
#         else:
#             return "Farmer not found"
#     else:
#         return "Access denied ! Log in first"


@app.route('/me/<farmer_id>')
def my_profile(farmer_id):
    # Check if the user is logged in by verifying the 'farmer_id' in the session
    if 'farmer_id' in session and str(session['farmer_id']) == farmer_id:
        # Fetch the farmer's details from MongoDB using the given ID
        new_farmer_info = mongo.db.users.find_one({'_id': ObjectId(farmer_id)})
        
        trade_listings = []
        if 'trade' in new_farmer_info and 'sell' in new_farmer_info['trade']:
            trade_ids = new_farmer_info['trade']['sell']
            if trade_ids:
                # Query trade data from the "trades" collection using the trade IDs
                trade_listings = mongo.db.trades.find({'_id': {'$in': trade_ids}})
        
        if new_farmer_info:
            return render_template('my_profile.html', new_farmer_info=new_farmer_info, trade_listings=trade_listings)
        else:
            return "Farmer not found"
    else:
        return "Access denied! Log in first"

    

@app.route('/logout')
def logout():
    # Clear the session data (log out the user)
    session.clear()
    # Redirect the user to the home page
    return redirect(url_for('index'))


@app.route('/sell')
def sell():
    return render_template('sell.html')

@app.route('/buy')
def buy():
    crops = mongo.db.trades.find()
    return render_template('buy.html',crops=crops)

@app.route('/sell_crops', methods=['POST'])
def sell_crops():
    if 'farmer_id' in session:
        if request.method == 'POST':
            # Get form data
            name =request.form['name']
            crop_image = request.files['crop_image']
            price_per_10kg = request.form['price_per_10kg']
            description = request.form['description']

            # Securely save the uploaded crop image to the defined folder
            crop_image_filename = secure_filename(crop_image.filename)
            crop_image.save(os.path.join(app.config['UPLOAD_FOLDER'], crop_image_filename))

            # Insert trade data into the "trades" collection
            trade_data = {
                'seller_id': ObjectId(session['farmer_id']),
                'name':name,
                'crop_image': crop_image_filename,
                'price_per_10kg': price_per_10kg,
                'description': description
            }
            trade_id = mongo.db.trades.insert_one(trade_data).inserted_id

            # Update the user's document in the "users" collection
            mongo.db.users.update_one(
                {'_id': ObjectId(session['farmer_id'])},
                {'$push': {'trade.sell': trade_id}}
            )

            # Redirect to the profile page after submission
            return redirect(url_for('index', farmer_id=session['farmer_id']))

    return "Access denied. Please log in."



@app.route('/buy_crops', methods=['GET', 'POST'])
def buy_crops():
    crops = []

    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        if crop_name:
            # Query the "trades" collection to get listings for the searched crop
            crops_list = list(mongo.db.trades.find({'name': crop_name}))

    return render_template('buy.html', crops_list=crops_list)


@app.route('/add_to_list', methods=['POST'])
def add_to_list():
    product_id = request.form.get('product_id')
    product = db.trades.find_one({'_id': ObjectId(product_id)})

    if product:
        product['price_per_10kg'] = float(product['price_per_10kg'])  # Convert to float

        cart = db.cart
        product_without_id = {key: value for key, value in product.items() if key != '_id'}
        cart.insert_one(product_without_id)

    return redirect(url_for('buy'))

@app.route('/delete/<string:item_id>')
def delete_item(item_id):
    shopping_list_collection.delete_one({'_id': ObjectId(item_id)})
    return redirect('/shopping_list')

@app.route('/clear_all', methods=['POST'])
def clear_all():
    shopping_list_collection.delete_many({})
    return redirect('/shopping_list')

@app.route('/shopping_list')
def shopping_list():
    shopping_list = list(shopping_list_collection.find())
    total_price = sum([product['price_per_10kg'] for product in shopping_list])
    return render_template('shopping_list.html', shopping_list=shopping_list, total_price=total_price)


########---------Hindi Routes-------########

@app.route('/hi')
def hindiindex():
    return render_template('index_hi.html')

@app.route('/hisignin')
def hindisignin():
    return render_template('signin_hi.html')

@app.route('/hisignup')
def hindisignup():
    return render_template('signup_hi.html')

@app.route('/hiabout')
def hindiin():
    return render_template('aboutus_hi.html')

@app.route('/hicontact')
def hindicontact():
    return render_template('contact_hi.html')

@app.route('/hipopup')
def hindipopup():
    return render_template('popup_hi.html')


@app.route('/himap', methods=['GET', 'POST'])
def himapindex():
    if request.method == 'POST':
        district = request.form['district'].strip()

        # Query the MongoDB database for the latitude and longitude of the given district
        # and store the results in a list of dictionaries
        locations = list(mongo.db.farmers.find({'district': district}, {'_id': 0, 'latitude': 1, 'longitude': 1}))
        if not locations:
            return render_template('mindex_hi.html', district=district, error='No records found for this district.')
        # Create a Folium map centered on the first location in the list
        map = folium.Map(location=[locations[0]['latitude'], locations[0]['longitude']], zoom_start=10)
        # Add markers for all the locations in the list
        for location in locations:
            # Query the MongoDB database for the user information
            row = mongo.db.farmers.find_one({'district': district, 'latitude': location['latitude'], 'longitude': location['longitude']})
            # Create a string with the user information to be displayed in the pop-up
            popup_html = f'<table style="width: 300px;"><tr><th>Farmer Name:</th><td>{row["full-name"]}</td></tr><tr><th>Phone No:</th><td>{row["phone"]}</td></tr><tr><th>Land size:</th><td>{row["landsize"]} acre</td></tr></table>'
            # Add a marker with the pop-up to the map
            folium.Marker(location=[location['latitude'], location['longitude']], popup=popup_html,icon=folium.Icon(color='darkgreen')).add_to(map)
        # Convert the map to HTML and pass it to the template
        map_html = map._repr_html_()
        return render_template('mindex_hi.html', district=district, map_html=map_html)

    # If the request method is not 'POST', return the default map page
    return render_template('mindex_hi.html', district='', map_html='', error='')

@app.route('/hifarmer')
def hifarmindex():
    return render_template('findex_hi.html')

@app.route('/hisubmit', methods=['POST'])
def hisubmit():
    if request.method == 'POST':
        fullName = request.form['full-name']
        Age = request.form['Age']
        email = request.form['email']
        phone = request.form['phone']
        district = request.form['district']
        taluka = request.form['taluka']
        landsize = request.form['landsize']
        address = request.form['address']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        otherinfo = request.form['other-info']
        mongo.db.farmers.insert_one({
            'full-name': fullName,
            'Age': Age,
            'email': email,
            'phone': phone,
            'district': district,
            'taluka': taluka,
            'landsize': landsize,
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'other-info': otherinfo
        })
        # Redirect to success page...
        return redirect(url_for('popup'))
    else:
        return 'Error'
    
    
@app.route('/hicrop')
def hicrop():
    return render_template('cindex_hi.html')

@app.route('/hichart', methods=['POST'])
def hichart():
    
    raw_data['DISTRICT_NAME'] = raw_data['DISTRICT_NAME'].str.replace(' ', '')
    district = request.form['district']
    df = raw_data[raw_data['DISTRICT_NAME'] == district]
    
    df_sum = df.append(df.sum(numeric_only=True), ignore_index=True)
    sum_row = df_sum.iloc[[-1]]
    n_row = sum_row.drop('DISTRICT_NAME', axis=1)
    p_row = n_row.drop('TALUKA_NAME', axis=1)
    q_row = p_row.astype(int)
    max_row = q_row.loc[q_row.sum(axis=1).idxmax()]
    max_col = max_row.idxmax()
    row_to_analyze = q_row.iloc[0]
    top_5 = row_to_analyze.nlargest(5).index.tolist()
    
    crop1 = request.form['crop1']
    crop2 = request.form['crop2']
    crop3 = request.form['crop3']
    crop4 = request.form['crop4']
    crop5 = request.form['crop5']

    selected_crops = [crop1, crop2, crop3, crop4, crop5]
    lat_df = sum_row[selected_crops]

    fig, (ax1, ax2) = plt.subplots(ncols=2, figsize=(20, 10))
    plt.figure(figsize=(8, 6))
    sns.set_style('whitegrid')
    palette = 'Paired'
    ax = sns.barplot(data=lat_df, palette=palette)
    ax.tick_params(labelsize=12)
    ax.set_xlabel('Crops', fontsize=14)
    ax.set_ylabel('Yield', fontsize=14)
    ax.set_title('Crop Yield by Crop Type', fontsize=18)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig('static/chart1.png')

    colors = sns.color_palette('Paired')
    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(lat_df.values[0], colors=colors, autopct='%1.1f%%', shadow=False, startangle=90, 
                                    wedgeprops=dict(width=0.6, edgecolor='w'))
    ax.set_title('Pie Chart', fontsize=15)
    ax.legend(wedges, lat_df.columns, title='Crops', loc='center left', bbox_to_anchor=(1, 0, 0.5, 1))
    plt.tight_layout()
    plt.savefig('static/chart2.png', bbox_inches='tight')

    # selected_crops = [crop1, crop2, crop3, crop4, crop5]
    top_districts = []
    for i in selected_crops:
        crop_data = raw_data[['DISTRICT_NAME'] + [i]]
        crop_data = crop_data.groupby('DISTRICT_NAME').sum().reset_index()
        crop_data['Total'] = crop_data[[i]].sum(axis=1)
        crop_data = crop_data.sort_values('Total', ascending=False).reset_index(drop=True)
        top_3 = crop_data.head(3)['DISTRICT_NAME'].tolist()
        top_districts.append((i, top_3))

    crops = []
    for crop in selected_crops:
        if lat_df[crop].iloc[0] == 0:
            crops.append((crop, f'does not grow in {district}.'))
        else:
            crops.append((crop, f'grows in {district}.'))

    return render_template('cindex_hi.html', crops=crops, max_crop=max_col, top_5=top_5, top_districts=top_districts)

#---------------Marathi Routes-------------

@app.route('/ma')
def marathiindex():
    return render_template('index_ma.html')

@app.route('/masignin')
def marathisignin():
    return render_template('signin_ma.html')

@app.route('/masignup')
def marathisignup():
    return render_template('signup_ma.html')

@app.route('/maabout')
def marathiin():
    return render_template('aboutus_ma.html')

@app.route('/macontact')
def marathicontact():
    return render_template('contact_ma.html')

@app.route('/mapopup')
def marathipopup():
    return render_template('popup_ma.html')

@app.route('/mamap', methods=['GET', 'POST'])
def mamapindex():
    if request.method == 'POST':
        district = request.form['district'].strip()

        # Query the MongoDB database for the latitude and longitude of the given district
        # and store the results in a list of dictionaries
        locations = list(mongo.db.farmers.find({'district': district}, {'_id': 0, 'latitude': 1, 'longitude': 1}))
        if not locations:
            return render_template('mindex_ma.html', district=district, error='No records found for this district.')
        # Create a Folium map centered on the first location in the list
        map = folium.Map(location=[locations[0]['latitude'], locations[0]['longitude']], zoom_start=10)
        # Add markers for all the locations in the list
        for location in locations:
            # Query the MongoDB database for the user information
            row = mongo.db.farmers.find_one({'district': district, 'latitude': location['latitude'], 'longitude': location['longitude']})
            # Create a string with the user information to be displayed in the pop-up
            popup_html = f'<table style="width: 300px;"><tr><th>Farmer Name:</th><td>{row["full-name"]}</td></tr><tr><th>Phone No:</th><td>{row["phone"]}</td></tr><tr><th>Land size:</th><td>{row["landsize"]} acre</td></tr></table>'
            # Add a marker with the pop-up to the map
            folium.Marker(location=[location['latitude'], location['longitude']], popup=popup_html).add_to(map)
        # Convert the map to HTML and pass it to the template
        map_html = map._repr_html_()
        return render_template('mindex_ma.html', district=district, map_html=map_html)

    # If the request method is not 'POST', return the default map page
    return render_template('mindex_ma.html', district='', map_html='', error='')

@app.route('/mafarmer')
def mafarmindex():
    return render_template('findex_ma.html')

@app.route('/masubmit', methods=['POST'])
def masubmit():
    if request.method == 'POST':
        fullName = request.form['full-name']
        Age = request.form['Age']
        email = request.form['email']
        phone = request.form['phone']
        district = request.form['district']
        taluka = request.form['taluka']
        landsize = request.form['landsize']
        address = request.form['address']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        otherinfo = request.form['other-info']
        mongo.db.farmers.insert_one({
            'full-name': fullName,
            'Age': Age,
            'email': email,
            'phone': phone,
            'district': district,
            'taluka': taluka,
            'landsize': landsize,
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'other-info': otherinfo
        })
        # Redirect to success page...
        return redirect(url_for('popup'))
    else:
        return 'Error'

@app.route('/macrop')
def macrop():
    return render_template('cindex_ma.html')

@app.route('/machart', methods=['POST'])
def machart():
    
    raw_data['DISTRICT_NAME'] = raw_data['DISTRICT_NAME'].str.replace(' ', '')
    district = request.form['district']
    df = raw_data[raw_data['DISTRICT_NAME'] == district]
    
    df_sum = df.append(df.sum(numeric_only=True), ignore_index=True)
    sum_row = df_sum.iloc[[-1]]
    n_row = sum_row.drop('DISTRICT_NAME', axis=1)
    p_row = n_row.drop('TALUKA_NAME', axis=1)
    q_row = p_row.astype(int)
    max_row = q_row.loc[q_row.sum(axis=1).idxmax()]
    max_col = max_row.idxmax()
    row_to_analyze = q_row.iloc[0]
    top_5 = row_to_analyze.nlargest(5).index.tolist()
    
    crop1 = request.form['crop1']
    crop2 = request.form['crop2']
    crop3 = request.form['crop3']
    crop4 = request.form['crop4']
    crop5 = request.form['crop5']

    selected_crops = [crop1, crop2, crop3, crop4, crop5]
    lat_df = sum_row[selected_crops]

    fig, (ax1, ax2) = plt.subplots(ncols=2, figsize=(20, 10))
    plt.figure(figsize=(8, 6))
    sns.set_style('whitegrid')
    palette = 'Paired'
    ax = sns.barplot(data=lat_df, palette=palette)
    ax.tick_params(labelsize=12)
    ax.set_xlabel('Crops', fontsize=14)
    ax.set_ylabel('Yield', fontsize=14)
    ax.set_title('Crop Yield by Crop Type', fontsize=18)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig('static/chart1.png')

    colors = sns.color_palette('Paired')
    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(lat_df.values[0], colors=colors, autopct='%1.1f%%', shadow=False, startangle=90, 
                                    wedgeprops=dict(width=0.6, edgecolor='w'))
    ax.set_title('Pie Chart', fontsize=15)
    ax.legend(wedges, lat_df.columns, title='Crops', loc='center left', bbox_to_anchor=(1, 0, 0.5, 1))
    plt.tight_layout()
    plt.savefig('static/chart2.png', bbox_inches='tight')

    # selected_crops = [crop1, crop2, crop3, crop4, crop5]
    top_districts = []
    for i in selected_crops:
        crop_data = raw_data[['DISTRICT_NAME'] + [i]]
        crop_data = crop_data.groupby('DISTRICT_NAME').sum().reset_index()
        crop_data['Total'] = crop_data[[i]].sum(axis=1)
        crop_data = crop_data.sort_values('Total', ascending=False).reset_index(drop=True)
        top_3 = crop_data.head(3)['DISTRICT_NAME'].tolist()
        top_districts.append((i, top_3))

    crops = []
    for crop in selected_crops:
        if lat_df[crop].iloc[0] == 0:
            crops.append((crop, f'does not grow in {district}.'))
        else:
            crops.append((crop, f'grows in {district}.'))

    return render_template('cindex_ma.html', crops=crops, max_crop=max_col, top_5=top_5, top_districts=top_districts)

@app.route('/sendpay', methods=['POST'])
def sendpay():
    return render_template('send_payment.html')

# Initialize Web3 and connect to MetaMask
w3 = Web3(Web3.HTTPProvider("https://eth-sepolia.g.alchemy.com/v2/-FVDY75dkPzWSA7WXVxnOqmXPoLtXn7b"))  # Replace with your Sepolia testnet RPC URL
w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # For PoA networks like Sepolia

# Replace with your contract address and ABI
contract_address = "0x596451Ae4b5778A8ec5ac6E91EAbfBAa3e4F11A4"
contract_abi = [
    {
        "inputs": [],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [],
        "name": "getContractBalance",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address payable",
                "name": "recipient",
                "type": "address"
            }
        ],
        "name": "sendEth",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

contract = w3.eth.contract(address=contract_address, abi=contract_abi)



@app.route('/send_payment', methods=['POST'])
def send_payment():
    sender_address = request.form.get('sender_address')
    recipient_address = request.form.get('recipient_address')
    amount_ether = float(request.form.get('amount_ether'))

    if not w3.isAddress(sender_address) or not w3.isAddress(recipient_address):
        return "Invalid sender or recipient address."

    if amount_ether <= 0:
        return "Invalid amount. Please enter a valid amount in ETH."

    amount_wei = w3.toWei(amount_ether, 'ether')
    gas_price = w3.toWei('10', 'gwei')  # Replace with an appropriate gas price

    try:
        transaction = contract.functions.sendEth(recipient_address).transact(
            {"from": sender_address, "value": amount_wei, "gas": 200000, "gasPrice": gas_price}
        )
        return f"Transaction sent. Transaction hash: {transaction.hex()}"
    except Exception as e:
        return f"Transaction failed: {str(e)}"




@app.route('/bridge')  # New route for Wormhole Connect
def bridge():
    return render_template('wormhole.html')













if __name__ == '__main__':
    app.run(port=5500, debug=True)