from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, flash
from flask_mysqldb import MySQL
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import uuid
# D:\Projects\MyMechanic2copy

app = Flask(__name__)


# Secret key for session management
app.secret_key = "your_secret_key"


# MySQL configuration
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'mymechanic1234'  # Replace with your password
app.config['MYSQL_DB'] = 'two_wheeler_vehicle'  # Database name
app.config['MYSQL_HOST'] = 'localhost'


mysql = MySQL(app)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


#-------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------------

def generate_session_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=20))


@app.route('/')
def home():
    cur = mysql.connection.cursor()

    # Fetch manufacturers
    cur.execute("SELECT manufacturer_id, name FROM manufacturers")
    manufacturers = cur.fetchall()

    # Fetch locations
    cur.execute("SELECT location_id, location_name FROM locations")
    locations = cur.fetchall()

    return render_template('home.html', manufacturers=manufacturers, locations=locations)

# Route to fetch models based on selected manufacturer
@app.route('/get_models', methods=['POST'])
def get_models():
    manufacturer_id = request.form.get('manufacturer_id')
    if manufacturer_id:
        cur = mysql.connection.cursor()
        cur.execute("SELECT model_id, modelname FROM models WHERE manufacturer_id = %s", (manufacturer_id,))
        models = cur.fetchall()

        # Returning dynamically created select options for models
        model_options = '<select name="model_id" id="model_id" class="w-full p-2 border border-gray-300 rounded">'
        model_options += '<option value="">Select Model</option>'
        for model in models:
            model_options += f'<option value="{model[0]}">{model[1]}</option>'
        model_options += '</select>'
        return model_options
    return ''

# Route to handle form submission
@app.route('/submit', methods=['POST'])
def submit():
    manufacturer_id = request.form.get('manufacturer_id')
    model_id = request.form.get('model_id')
    location_id = 1  # Default location
    phone = request.form.get('phone_number')
    request_time = datetime.now()

    # Save form data to the user_requests table
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO user_requests (manufacturer_id, model_id, location_id, phone, request_time)
        VALUES (%s, %s, %s, %s, %s)
    """, (manufacturer_id, model_id, location_id, phone, request_time))
    mysql.connection.commit()

    # Set request_id in session
    session['request_id'] = cur.lastrowid  # Save the request_id of the newly inserted record

    flash("Request submitted successfully!", "success")

    # Redirect to the service page with query parameters
    return redirect(url_for('service', manufacturer_id=manufacturer_id, model_id=model_id, location_id=location_id))


@app.route('/service', methods=['GET'])
def service():
    manufacturer_id = request.args.get('manufacturer_id')
    model_id = request.args.get('model_id')
    location_id = int(request.args.get('location_id', default='1'))  # Default location_id is set to 1
    category_id = request.args.get('category_id')

    # Create a new user request and save it to the user_requests table
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO user_requests (manufacturer_id, model_id, location_id, phone)
        VALUES (%s, %s, %s, %s)
    """, (manufacturer_id, model_id, location_id, request.args.get('phone')))
    mysql.connection.commit()

    # Get the request_id of the newly created request
    cur.execute("SELECT LAST_INSERT_ID()")
    request_id = cur.fetchone()[0]

    # Store the request_id in the session
    session['request_id'] = request_id

    # Fetch services and categories
    query = """
        SELECT s.service_id, s.name, s.description, s.price, s.duration, s.image_url
        FROM services s
        WHERE s.manufacturer_id = %s AND s.model_id = %s AND s.location_id = %s
    """
    if category_id:
        query += " AND s.category_id = %s"

    cur.execute(query, (manufacturer_id, model_id, location_id, category_id) if category_id else (manufacturer_id, model_id, location_id))
    services = cur.fetchall()

    cur.execute("SELECT category_id, category_name FROM service_categories")
    categories = cur.fetchall()

    if services:
        return render_template('services.html', services=services, categories=categories)
    else:
        return "No services found for the selected manufacturer and model."

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    service_id = request.form['service_id']
    price = request.form['price']
    request_id = session.get('request_id')  # Assuming the user request ID is stored in the session

    # Check if the request_id exists in the session (if not, return an error)
    if not request_id:
        return "No user request found", 400

    # Check if the service has already been added to the cart
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT * FROM cart WHERE request_id = %s AND service_id = %s
    """, (request_id, service_id))
    existing_service = cur.fetchone()

    if existing_service:
        return "This service is already in your cart", 400

    # Check if the user has already selected a service from the same category
    cur.execute("""
        SELECT c.service_id FROM cart c
        JOIN services s ON c.service_id = s.service_id
        WHERE c.request_id = %s AND s.category_id = (SELECT category_id FROM services WHERE service_id = %s)
    """, (request_id, service_id))
    existing_category_service = cur.fetchone()

    if existing_category_service:
        return "You can only choose one service from each category", 400

    # Add the service to the cart
    cur.execute("""
        INSERT INTO cart (request_id, service_id, price)
        VALUES (%s, %s, %s)
    """, (request_id, service_id, price))
    mysql.connection.commit()

    return 'Service added to cart', 200

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    service_id = request.form['service_id']
    request_id = session.get('request_id')

    if not request_id:
        return "No user request found", 400

    # Remove the service from the cart
    cur = mysql.connection.cursor()
    cur.execute("""
        DELETE FROM cart WHERE request_id = %s AND service_id = %s
    """, (request_id, service_id))
    mysql.connection.commit()

    return 'Service removed from cart', 200

@app.route('/get_cart', methods=['GET'])
def get_cart():
    request_id = session.get('request_id')
    if not request_id:
        return jsonify([])

    # Fetch cart items from the database
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT s.service_id, s.name AS service_name, c.price
        FROM cart c
        JOIN services s ON c.service_id = s.service_id
        WHERE c.request_id = %s
    """, (request_id,))
    cart_items = cur.fetchall()

    # Convert to JSON-friendly format
    cart_data = [{'service_id': item[0], 'service_name': item[1], 'price': item[2]} for item in cart_items]
    
    return jsonify(cart_data)


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    request_id = session.get('request_id')
    if not request_id:
        return redirect(url_for('service'))  # Redirect to service page if no user request exists in session

    # Fetch the cart items for the current request
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT s.service_id, s.name AS service_name, c.price
        FROM cart c
        JOIN services s ON c.service_id = s.service_id
        WHERE c.request_id = %s
    """, (request_id,))
    cart_items = cur.fetchall()

    if not cart_items:
        return "Your cart is empty. Please add services to your cart.", 400

    # Calculate the total price
    total_price = sum(item[2] for item in cart_items)

    if request.method == 'POST':
        # Handle form submission for order confirmation
        user_name = request.form['user_name']
        user_phone = request.form['user_phone']
        user_address = request.form['user_address']

        # Create an order entry
        cur.execute("""
            INSERT INTO orders (request_id, total_price, user_name, user_phone, user_address, order_date)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (request_id, total_price, user_name, user_phone, user_address))
        mysql.connection.commit()

        # Optionally, you can clear the cart after order confirmation
        cur.execute("""
            DELETE FROM cart WHERE request_id = %s
        """, (request_id,))
        mysql.connection.commit()

        return "Your order has been confirmed! Thank you for choosing our service."

    # Render checkout page with cart items and total price
    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)




#--------------------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------------------
# Helper function to get request_id from session
# Add item to cart




#--------------------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------------------


# Admin Panel - Dashboard
@app.route('/admin')
def admin_dashboard():
    cur = mysql.connection.cursor()

    # Fetch counts for the admin dashboard
    cur.execute("SELECT COUNT(*) FROM manufacturers")
    manufacturers_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM models")
    models_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations")
    locations_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM user_requests")
    requests_count = cur.fetchone()[0]

    return render_template(
        'admin.html',
        manufacturers_count=manufacturers_count,
        models_count=models_count,
        locations_count=locations_count,
        requests_count=requests_count
    )

#--------------------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------------------


# Admin Panel - Manage Manufacturers
@app.route('/admin/manufacturers')
def manage_manufacturers():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM manufacturers")
    manufacturers = cur.fetchall()
    return render_template('manufacturers.html', manufacturers=manufacturers)



# Add Manufacturer
@app.route('/admin/manufacturers/add', methods=['GET', 'POST'])
def add_manufacturer():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO manufacturers (name) VALUES (%s)", (name,))
            mysql.connection.commit()
            flash("Manufacturer added successfully!", "success")
            return redirect(url_for('manage_manufacturers'))

    return render_template('add_manufacturer.html')



# Edit Manufacturer
@app.route('/admin/manufacturers/edit/<int:manufacturer_id>', methods=['GET', 'POST'])
def edit_manufacturer(manufacturer_id):
    cur = mysql.connection.cursor()
    
    # Fetch manufacturer data for editing
    cur.execute("SELECT * FROM manufacturers WHERE manufacturer_id = %s", (manufacturer_id,))
    manufacturer = cur.fetchone()

    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            cur.execute("UPDATE manufacturers SET name = %s WHERE manufacturer_id = %s", (name, manufacturer_id))
            mysql.connection.commit()
            flash("Manufacturer updated successfully!", "success")
            return redirect(url_for('manage_manufacturers'))

    return render_template('edit_manufacturer.html', manufacturer=manufacturer)



# Delete Manufacturer
@app.route('/admin/manufacturers/delete/<int:manufacturer_id>', methods=['GET'])
def delete_manufacturer(manufacturer_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM manufacturers WHERE manufacturer_id = %s", (manufacturer_id,))
    mysql.connection.commit()
    flash("Manufacturer deleted successfully!", "success")
    return redirect(url_for('manage_manufacturers'))



# Search Manufacturer
@app.route('/admin/manufacturers/search', methods=['GET'])
def search_manufacturer():
    search_term = request.args.get('search', '').strip()
    cur = mysql.connection.cursor()
    if search_term:
        cur.execute("SELECT * FROM manufacturers WHERE name LIKE %s", ('%' + search_term + '%',))
    else:
        cur.execute("SELECT * FROM manufacturers")
    manufacturers = cur.fetchall()
    return render_template('manufacturers.html', manufacturers=manufacturers)

#--------------------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------

# Route to manage models
@app.route('/admin/models', methods=['GET', 'POST'])
def manage_models():
    search_query = request.args.get('search', '')
    manufacturer_id = request.args.get('manufacturer_id', '')

    cur = mysql.connection.cursor()

    # Base query
    query = """
        SELECT model_id, ModelName, type, manufacturers.name
        FROM models
        JOIN manufacturers ON models.manufacturer_id = manufacturers.manufacturer_id
        WHERE ModelName LIKE %s
    """

    # Add filter for manufacturer if provided
    if manufacturer_id:
        query += " AND manufacturers.manufacturer_id = %s"
        cur.execute(query, ('%' + search_query + '%', manufacturer_id))
    else:
        cur.execute(query, ('%' + search_query + '%',))

    models = cur.fetchall()

    # Fetch all manufacturers for the filter dropdown
    cur.execute("SELECT manufacturer_id, name FROM manufacturers")
    manufacturers = cur.fetchall()

    return render_template('models.html', models=models, manufacturers=manufacturers, search_query=search_query, selected_manufacturer=manufacturer_id)



# Add Model
@app.route('/admin/models/add', methods=['GET', 'POST'])
def add_model():
    if request.method == 'POST':
        manufacturer_id = request.form.get('manufacturer_id')
        model_name = request.form.get('model_name')
        model_type = request.form.get('model_type')

        if manufacturer_id and model_name and model_type:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO models (manufacturer_id, ModelName, type) VALUES (%s, %s, %s)",
                (manufacturer_id, model_name, model_type)
            )
            mysql.connection.commit()
            flash("Model added successfully!", "success")
            return redirect(url_for('manage_models'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT manufacturer_id, name FROM manufacturers")
    manufacturers = cur.fetchall()

    return render_template('add_model.html', manufacturers=manufacturers)
 


# Edit Model
@app.route('/admin/models/edit/<int:model_id>', methods=['GET', 'POST'])
def edit_model(model_id):
    cur = mysql.connection.cursor()

    # Fetch model details
    cur.execute("""
        SELECT model_id, ModelName, type, manufacturer_id
        FROM models
        WHERE model_id = %s
    """, (model_id,))
    model = cur.fetchone()

    # Fetch all manufacturers for dropdown
    cur.execute("SELECT manufacturer_id, name FROM manufacturers")
    manufacturers = cur.fetchall()

    if request.method == 'POST':
        manufacturer_id = request.form.get('manufacturer_id')
        model_name = request.form.get('model_name')
        model_type = request.form.get('model_type')

        if manufacturer_id and model_name and model_type:
            cur.execute("""
                UPDATE models
                SET manufacturer_id = %s, ModelName = %s, type = %s
                WHERE model_id = %s
            """, (manufacturer_id, model_name, model_type, model_id))
            mysql.connection.commit()
            flash("Model updated successfully!", "success")
            return redirect(url_for('manage_models'))

        flash("All fields are required!", "error")

    return render_template('edit_model.html', model=model, manufacturers=manufacturers)



# Delete Model
@app.route('/admin/models/delete/<int:model_id>', methods=['POST'])
def delete_model(model_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM models WHERE model_id = %s", (model_id,))
    mysql.connection.commit()
    flash("Model deleted successfully!", "success")
    return redirect(url_for('manage_models'))

#--------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------

@app.route('/admin/locations', methods=['GET'])
def manage_locations():
    search_query = request.args.get('search', '').lower()
    cursor = mysql.connection.cursor()
    
    if search_query:
        cursor.execute(
            "SELECT location_id, location_name FROM Locations WHERE LOWER(location_name) LIKE %s",
            (f"%{search_query}%",)
        )
    else:
        cursor.execute("SELECT location_id, location_name FROM Locations")
    
    locations = cursor.fetchall()
    cursor.close()
    return render_template('locations.html', locations=locations)

@app.route('/admin/locations/add', methods=['GET', 'POST'])
def add_location():
    if request.method == 'POST':
        location_name = request.form.get('location_name')
        
        if not location_name:
            flash('Location name cannot be empty.', 'danger')
            return redirect(url_for('add_location'))
        
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO Locations (location_name) VALUES (%s)",
            (location_name,)
        )
        mysql.connection.commit()
        cursor.close()
        
        flash('Location added successfully!', 'success')
        return redirect(url_for('manage_locations'))
    
    return render_template('add_location.html')

@app.route('/admin/locations/edit/<int:location_id>', methods=['GET', 'POST'])
def edit_location(location_id):
    cursor = mysql.connection.cursor()
    
    if request.method == 'POST':
        location_name = request.form.get('location_name')
        
        if not location_name:
            flash('Location name cannot be empty.', 'danger')
            return redirect(url_for('edit_location', location_id=location_id))
        
        cursor.execute(
            "UPDATE Locations SET location_name = %s WHERE location_id = %s",
            (location_name, location_id)
        )
        mysql.connection.commit()
        cursor.close()
        
        flash('Location updated successfully!', 'success')
        return redirect(url_for('manage_locations'))
    
    cursor.execute("SELECT location_id, location_name FROM Locations WHERE location_id = %s", (location_id,))
    location = cursor.fetchone()
    cursor.close()
    
    if not location:
        flash('Location not found.', 'danger')
        return redirect(url_for('manage_locations'))
    
    return render_template('edit_location.html', location=location)

@app.route('/admin/locations/delete/<int:location_id>', methods=['POST'])
def delete_location(location_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM Locations WHERE location_id = %s", (location_id,))
    mysql.connection.commit()
    cursor.close()
    
    flash('Location deleted successfully!', 'success')
    return redirect(url_for('manage_locations'))

#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------

# Manage Products
@app.route('/admin/products')
def manage_products():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM products")
    columns = [col[0] for col in cursor.description]  # Get column names
    products = cursor.fetchall()

    # Manually map tuples to dictionaries
    products_dict = []
    for product in products:
        product_dict = dict(zip(columns, product))  # Map column names to tuple values
        products_dict.append(product_dict)

    cursor.close()
    return render_template('products.html', products=products_dict)


@app.route('/admin/manage_products/add_product', methods=['GET', 'POST'])
def add_product_form():
    if request.method == 'POST':
        # Get form data
        category_id = request.form['category_id']
        manufacturer_id = request.form['manufacturer_id']
        model_id = request.form['model_id']
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        quantity = request.form['quantity']
        item_code = request.form['item_code']
        image_url = request.files['image_url']

        # Handle image file upload (optional)
        if image_url:
            image_filename = image_url.filename
            image_url.save(os.path.join('static/uploads', image_filename))
        else:
            image_filename = None  # Default to None if no image is uploaded

        # Insert product data into the database
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO products (name, description, price, quantity, category_id, manufacturer_id, model_id, item_code, image_url) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (name, description, price, quantity, category_id, manufacturer_id, model_id, item_code, image_filename)
        )
        mysql.connection.commit()
        cur.close()

        # Redirect to manage products page
        return redirect(url_for('manage_products'))

    # If GET request, render form
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM product_categories")
    categories = cur.fetchall()
    cur.execute("SELECT * FROM manufacturers")
    manufacturers = cur.fetchall()
    cur.close()
    return render_template('add_product.html', categories=categories, manufacturers=manufacturers)



@app.route('/admin/manage_products/get_models/<manufacturer_id>', methods=['GET'])
def products_get_models(manufacturer_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT model_id, ModelName FROM models WHERE manufacturer_id = %s", [manufacturer_id])
    models = cur.fetchall()
    cur.close()

    # Print models to check what is being returned
     # Debugging line

    models_list = [{"model_id": model[0], "ModelName": model[1]} for model in models]
    return jsonify(models_list)


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    # Code to edit product using the product_id
    return render_template('edit_product.html', product_id=product_id)


# Delete Product
@app.route('/admin/products/delete/<int:product_id>', methods=['GET'])
def delete_product(product_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM products WHERE product_id = %s", [product_id])
    mysql.connection.commit()
    cur.close()

    flash('Product deleted successfully!', 'success')
    return redirect(url_for('manage_products'))


#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------

@app.route('/admin/blog', methods=['GET'])
def manage_blog():
    # Get the search query from the request
    search_query = request.args.get('search', '').strip()

    cursor = mysql.connection.cursor()

    # Base SQL query
    query = "SELECT blog_id, title, content, image_url FROM blogs WHERE 1=1"
    args = []

    # If search query is provided, add search condition
    if search_query:
        query += " AND (title LIKE %s OR content LIKE %s)"
        args.extend([f"%{search_query}%", f"%{search_query}%"])

    # Execute the query with search filter
    cursor.execute(query, args)
    result = cursor.fetchall()

    # Convert tuples to dictionaries
    blogs = [
        {"blog_id": row[0], "title": row[1], "content": row[2], "image_url": row[3]} 
        for row in result
    ]

    cursor.close()
    return render_template(
        'adminblog.html',
        blogs=blogs,
        search_query=search_query
    )


@app.route('/admin/blog/add', methods=['GET', 'POST'])
def add_blog():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image_url = request.form['image_url']

        cursor = mysql.connection.cursor()
        query = "INSERT INTO blogs (title, content, image_url) VALUES (%s, %s, %s)"
        cursor.execute(query, (title, content, image_url))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('manage_blog'))

    return render_template('add_blog.html')



@app.route('/admin/blog/edit/<int:blog_id>', methods=['GET', 'POST'])
def edit_blog(blog_id):
    cursor = mysql.connection.cursor()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image_url = request.form['image_url']

        query = "UPDATE blogs SET title = %s, content = %s, image_url = %s WHERE blog_id = %s"
        cursor.execute(query, (title, content, image_url, blog_id))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('manage_blog'))

    # Fetch blog details for editing
    query = "SELECT blog_id, title, content, image_url FROM blogs WHERE blog_id = %s"
    cursor.execute(query, (blog_id,))
    blog = cursor.fetchone()
    cursor.close()

    if blog:
        blog_data = {"blog_id": blog[0], "title": blog[1], "content": blog[2], "image_url": blog[3]}
        return render_template('edit_blog.html', blog=blog_data)
    else:
        return "Blog not found", 404

    

@app.route('/admin/blog/delete/<int:blog_id>', methods=['GET', 'POST'])
def delete_blog(blog_id):
    cursor = mysql.connection.cursor()
    query = "DELETE FROM blogs WHERE blog_id = %s"
    cursor.execute(query, (blog_id,))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('manage_blog'))



#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------



#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------

@app.route('/blog')
def blog():
    cur = mysql.connection.cursor()
    cur.execute("SELECT blog_id, title, content, image_url FROM blogs")
    blogs = cur.fetchall()
    cur.close()
    return render_template('blog.html', blogs=blogs)


@app.route('/blog/<int:blog_id>')
def blog_post(blog_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT title, content, image_url FROM blogs WHERE blog_id = %s", (blog_id,))
    blog = cur.fetchone()
    cur.close()
    return render_template('blog_post.html', blog=blog)


#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------

@app.route('/admin/user_requests')
def user_requests():
    cur = mysql.connection.cursor()
    # SQL query to fetch names instead of IDs by joining tables
    cur.execute("""
        SELECT ur.request_id, 
               m.name AS manufacturer_name, 
               mo.ModelName AS model_name, 
               l.location_name AS location_name,
               ur.phone, 
               ur.request_time 
        FROM User_requests ur
        JOIN Manufacturers m ON ur.manufacturer_id = m.manufacturer_id
        JOIN Models mo ON ur.model_id = mo.model_id
        JOIN Locations l ON ur.location_id = l.location_id
    """)
    user_requests_data = cur.fetchall()
    cur.close()
    return render_template('user_requests.html', user_requests=user_requests_data)

@app.route('/admin/user_requests/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    cur = mysql.connection.cursor()
    # SQL query to delete the record based on request_id
    cur.execute("DELETE FROM User_requests WHERE request_id = %s", (request_id,))
    mysql.connection.commit()
    cur.close()
    # Redirect back to the user requests page after deletion
    return redirect(url_for('user_requests'))


#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------


@app.route('/faq')
def faq():
    return render_template('faq.html')

#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------

@app.route('/contact')
def contact():
    return render_template('contact.html')


#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------
# Route to manage services
@app.route('/admin/manage_services')
def manage_services():
    # Initialize cursor
    cur = mysql.connection.cursor()

    # Execute the query
    cur.execute("""
        SELECT s.service_id, s.name, s.description, s.price, s.duration, s.image_url, 
               c.category_name, m.ModelName, l.location_name
        FROM services s
        JOIN service_categories c ON s.category_id = c.category_id
        JOIN models m ON s.model_id = m.model_id
        JOIN locations l ON s.location_id = l.location_id
    """)

    # Fetch all the results
    results = cur.fetchall()

    # Define the column names (this should match the SELECT query columns)
    columns = ['service_id', 'name', 'description', 'price', 'duration', 'image_url', 'category_name', 'ModelName', 'location_name']

    # Convert tuples to dictionaries
    services = [dict(zip(columns, result)) for result in results]

    # Close the cursor
    cur.close()

    # Pass the services data to the template
    return render_template('admin_services.html', services=services)


# Route to render add service form
@app.route('/admin/manage_services/add_service', methods=['GET'])
def add_service_form():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM service_categories")
    categories = cur.fetchall()
    cur.execute("SELECT * FROM manufacturers")
    manufacturers = cur.fetchall()
    cur.execute("SELECT * FROM locations")
    locations = cur.fetchall()
    cur.close()
    return render_template('add_services.html', categories=categories, manufacturers=manufacturers, locations=locations)

@app.route('/admin/manage_services/get_models/<manufacturer_id>', methods=['GET'])
def services_get_models(manufacturer_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT model_id, ModelName FROM models WHERE manufacturer_id = %s", [manufacturer_id])
    models = cur.fetchall()
    cur.close()

    # Print models to check what is being returned
     # Debugging line

    models_list = [{"model_id": model[0], "ModelName": model[1]} for model in models]
    return jsonify(models_list)


# Route to handle adding a new service
@app.route('/admin/add_service', methods=['GET', 'POST'])
def add_service():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category_id = request.form['category_id']
        manufacturer_id = request.form['manufacturer_id']
        model_id = request.form['model_id']
        price = request.form['price']
        duration = request.form['duration']
        location_id = request.form['location_id']
        
        # Handle image upload
        image_url = None
        if 'image_url' in request.files:
            file = request.files['image_url']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f"uploads/{filename}"
        
        # Save data to the database
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO services (name, description, category_id, manufacturer_id, model_id, 
                                  price, duration, location_id, image_url) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, description, category_id, manufacturer_id, model_id, price, duration, location_id, image_url))
        mysql.connection.commit()
        cur.close()
        
        flash("Service added successfully", "success")
        return redirect(url_for('manage_services'))
    
    # Load categories, manufacturers, and locations for the form
    cur = mysql.connection.cursor()
    cur.execute("SELECT category_id, category_name FROM service_categories")
    categories = cur.fetchall()

    cur.execute("SELECT manufacturer_id, name FROM manufacturers")
    manufacturers = cur.fetchall()

    cur.execute("SELECT location_id, location_name FROM locations")
    locations = cur.fetchall()

    cur.close()
    return render_template('add_services.html', categories=categories, manufacturers=manufacturers, locations=locations)


# Route to edit a service
@app.route('/admin/manage_services/edit_service/<int:service_id>', methods=['GET', 'POST'])
def edit_service(service_id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        duration = request.form['duration']
        category_id = request.form['category_id']
        model_id = request.form['model_id']
        location_id = request.form['location_id']
        image_url = request.form['image_url']

        cur.execute('''UPDATE services 
                       SET name = %s, description = %s, price = %s, duration = %s, 
                           category_id = %s, model_id = %s, location_id = %s, image_url = %s 
                       WHERE service_id = %s''', 
                    (name, description, price, duration, category_id, model_id, location_id, image_url, service_id))
        mysql.connection.commit()
        cur.close()
        flash('Service updated successfully', 'success')
        return redirect(url_for('manage_services'))

    cur.execute('''SELECT * FROM services WHERE service_id = %s''', [service_id])
    service = cur.fetchone()
    cur.execute('SELECT * FROM service_categories')
    categories = cur.fetchall()
    cur.execute('SELECT * FROM models')
    models = cur.fetchall()
    cur.execute('SELECT * FROM locations')
    locations = cur.fetchall()
    cur.close()

    return render_template('edit_services.html', service=service, categories=categories, models=models, locations=locations)


# Route to delete a service
@app.route('/admin/manage_services/delete_service/<int:service_id>', methods=['GET'])
def delete_service(service_id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM services WHERE service_id = %s', [service_id])
    mysql.connection.commit()
    cur.close()
    flash('Service deleted successfully', 'success')
    return redirect(url_for('manage_services'))




#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------
@app.route('/shop')
def shop():
    return render_template('shop.html')

@app.route('/api/manufacturers', methods=['GET'])
def fetch_manufacturers():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT manufacturer_id, name FROM manufacturers")
    manufacturers = cursor.fetchall()
    cursor.close()
    return jsonify([{'id': m[0], 'name': m[1]} for m in manufacturers])

@app.route('/api/models/<manufacturer_id>', methods=['GET'])
def fetch_models(manufacturer_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT model_id, ModelName FROM models WHERE manufacturer_id = %s", (manufacturer_id,))
    models = cursor.fetchall()
    cursor.close()
    return jsonify([{'id': m[0], 'name': m[1]} for m in models])

@app.route('/api/categories', methods=['GET'])
def fetch_categories():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT category_id, category_name FROM product_categories")
    categories = cursor.fetchall()
    cursor.close()
    return jsonify([{'id': c[0], 'name': c[1]} for c in categories])

@app.route('/api/products', methods=['GET'])
def fetch_products():
    manufacturer_id = request.args.get('manufacturer_id')
    model_id = request.args.get('model_id')
    category_id = request.args.get('category_id')

    query = """
        SELECT p.name, p.description, p.price, p.image_url
        FROM products p
        LEFT JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id
        LEFT JOIN models mo ON p.model_id = mo.model_id
        LEFT JOIN product_categories c ON p.category_id = c.category_id
        WHERE 1=1
    """
    params = []

    if manufacturer_id:
        query += " AND p.manufacturer_id = %s"
        params.append(manufacturer_id)

    if model_id:
        query += " AND p.model_id = %s"
        params.append(model_id)

    if category_id:
        query += " AND p.category_id = %s"
        params.append(category_id)

    cursor = mysql.connection.cursor()
    cursor.execute(query, tuple(params))
    products = cursor.fetchall()
    cursor.close()

    return jsonify([{'name': p[0], 'description': p[1], 'price': p[2], 'image_url': p[3]} for p in products])


#--------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
