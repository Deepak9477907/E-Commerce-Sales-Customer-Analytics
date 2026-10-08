CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    customer_unique_id TEXT,
    customer_zip_code_prefix INT,
    customer_city TEXT,
    customer_state TEXT
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT,
    order_status TEXT,
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

CREATE TABLE order_items (
    order_id TEXT,
    order_item_id INT,
    product_id TEXT,
    seller_id TEXT,
    shipping_limit_date TIMESTAMP,
    price NUMERIC(12,2),
    freight_value NUMERIC(12,2)
);

CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    product_category_name TEXT,
    product_name_lenght INT,
    product_description_lenght INT,
    product_photos_qty INT,
    product_weight_g NUMERIC,
    product_length_cm NUMERIC,
    product_height_cm NUMERIC,
    product_width_cm NUMERIC
);

CREATE TABLE sellers (
    seller_id TEXT PRIMARY KEY,
    seller_zip_code_prefix INT,
    seller_city TEXT,
    seller_state TEXT
);

CREATE TABLE order_payments (
    order_id TEXT,
    payment_sequential INT,
    payment_type TEXT,
    payment_installments INT,
    payment_value NUMERIC(12,2)
);

CREATE TABLE order_reviews (
    review_id TEXT,
    order_id TEXT,
    review_score INT,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

CREATE TABLE category_translation (
    product_category_name TEXT,
    product_category_name_english TEXT
);
--===============================================================================
select count(*) as total_customers 
from customers;

select * from customers
limit 5;
--------------------------------------------------------
SELECT COUNT(*) AS total_orders
FROM orders;

SELECT *
FROM orders
LIMIT 5;
--------------------------------------------------------
SELECT COUNT(*) AS total_order_items
FROM order_items;

SELECT *
FROM order_items
LIMIT 5;
--------------------------------------------------------
--1)Step 1 — Check orders without matching customers

SELECT COUNT(*) AS unmatched_orders
FROM orders o
LEFT JOIN customers c
    ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

--2)check order items without matching orders

SELECT COUNT(*) AS unmatched_order_items
FROM order_items oi
LEFT JOIN orders o
    ON oi.order_id = o.order_id
WHERE o.order_id IS NULL;
--------------------------------------------------------
--3)Step 3 — Our first real 3-table JOIN

SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    oi.order_item_id,
    oi.product_id,
    oi.price,
    oi.freight_value
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
JOIN order_items oi
    ON o.order_id = oi.order_id
LIMIT 10;
--------------------------------------------------------

SELECT COUNT(*) AS products_count FROM products;

SELECT COUNT(*) AS sellers_count FROM sellers;

SELECT COUNT(*) AS payments_count FROM order_payments;

SELECT COUNT(*) AS reviews_count FROM order_reviews;

SELECT COUNT(*) AS categories_count FROM category_translation;



