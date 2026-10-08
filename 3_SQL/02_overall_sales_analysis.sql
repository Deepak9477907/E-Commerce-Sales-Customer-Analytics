-- ===============================================================================
-- OVERALL SALES & DELIVERY PERFORMANCE ANALYSIS
-- ===============================================================================

-- 1) Total number of orders
SELECT COUNT(*) AS total_orders 
FROM orders;

-- 2) Number of delivered orders
SELECT COUNT(order_status) AS delivered_orders 
FROM orders
WHERE order_status = 'delivered';

-- 3) Number of canceled orders
SELECT COUNT(order_status) AS canceled_orders 
FROM orders
WHERE order_status = 'canceled';

-- 4) Number of orders for each order_status
SELECT 
    order_status,
    COUNT(*) AS order_count
FROM orders
GROUP BY order_status
ORDER BY order_count DESC;

-- 5) Total merchandise sales value across all order items
SELECT SUM(price) AS total_merchandise_sales_value
FROM order_items;

-- 6) Total freight value across all order items
SELECT SUM(freight_value) AS total_freight_value
FROM order_items;

-- 7) Total amount customers actually paid across all payment records
SELECT SUM(payment_value) AS customer_actually_paid
FROM order_payments;

-- 8) Average amount paid per order (Fixed trailing GROUP BY syntax error)
WITH order_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS total_payment
    FROM order_payments
    GROUP BY order_id
)
SELECT ROUND(AVG(total_payment), 2) AS avg_payment_value
FROM order_totals;

-- 9) Payment summary by payment type
SELECT 
    payment_type,
    COUNT(DISTINCT order_id) AS unique_orders,
    SUM(payment_value) AS total_payment_value
FROM order_payments
GROUP BY payment_type
ORDER BY total_payment_value DESC;

-- 10) Payment type percentage share of overall payment value
SELECT 
    payment_type, 
    COUNT(DISTINCT order_id) AS unique_orders,
    SUM(payment_value) AS total_payment_value,
    ROUND(
        SUM(payment_value) * 100.0 / (SELECT SUM(payment_value) FROM order_payments), 
        2
    ) AS payment_percentage
FROM order_payments
GROUP BY payment_type
ORDER BY total_payment_value DESC;

-- 11) Orders that used more than one payment type
SELECT 
    order_id,
    COUNT(DISTINCT payment_type) AS unique_payment_type
FROM order_payments
GROUP BY order_id
HAVING COUNT(DISTINCT payment_type) > 1
ORDER BY unique_payment_type DESC;

-- 12) Top 10 orders with the highest total payment value
SELECT 
    order_id,
    SUM(payment_value) AS total_payment_value
FROM order_payments
GROUP BY order_id
ORDER BY total_payment_value DESC
LIMIT 10;

-- 13) Average total payment per order
WITH orders_summary AS (
    SELECT 
        order_id,
        SUM(payment_value) AS total_payment_value
    FROM order_payments
    GROUP BY order_id
)
SELECT ROUND(AVG(total_payment_value), 2) AS avg_payment_per_order
FROM orders_summary;

-- 14) Orders placed per month
SELECT 
    TO_CHAR(order_purchase_timestamp, 'YYYY-MM') AS purchase_month,
    COUNT(*) AS total_orders
FROM orders
WHERE order_purchase_timestamp IS NOT NULL
GROUP BY TO_CHAR(order_purchase_timestamp, 'YYYY-MM')
ORDER BY purchase_month ASC;

-- 15) Total payment value by purchase month
SELECT 
    TO_CHAR(o.order_purchase_timestamp, 'YYYY-MM') AS purchase_month,
    SUM(op.payment_value) AS payment_value_by_purchase_month
FROM orders o 	   
JOIN order_payments op 
    ON o.order_id = op.order_id  
WHERE o.order_purchase_timestamp IS NOT NULL
GROUP BY TO_CHAR(o.order_purchase_timestamp, 'YYYY-MM')
ORDER BY purchase_month ASC;

-- 16) Total orders placed in November 2016
SELECT COUNT(*) AS total_orders
FROM orders
WHERE order_purchase_timestamp >= '2016-11-01'
  AND order_purchase_timestamp < '2016-12-01';

-- 17) Monthly payment value with prior month comparison (Fixed LAG bug)
WITH monthly_payments AS (
    SELECT
        DATE_TRUNC('month', o.order_purchase_timestamp) AS purchase_month,
        SUM(op.payment_value) AS total_payment_value
    FROM orders o
    JOIN order_payments op
        ON o.order_id = op.order_id
    WHERE o.order_purchase_timestamp IS NOT NULL
    GROUP BY DATE_TRUNC('month', o.order_purchase_timestamp)
),
previous_values AS (
    SELECT
        purchase_month,
        total_payment_value,
        LAG(purchase_month) OVER (ORDER BY purchase_month) AS previous_month,
        LAG(total_payment_value) OVER (ORDER BY purchase_month) AS previous_payment
    FROM monthly_payments
)
SELECT
    TO_CHAR(purchase_month, 'YYYY-MM') AS purchase_month,
    total_payment_value,
    CASE
        WHEN previous_month = purchase_month - INTERVAL '1 month'
        THEN previous_payment
        ELSE NULL
    END AS previous_month_payment
FROM previous_values
ORDER BY purchase_month;

-- 18) Payment value associated with each order status
SELECT 
    o.order_status,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(op.payment_value) AS total_payment_value
FROM orders o 	   
JOIN order_payments op 
    ON o.order_id = op.order_id 
GROUP BY o.order_status
ORDER BY total_payment_value DESC;

-- 19) Top 10 product categories by merchandise sales value (delivered orders)
SELECT 
    p.product_category_name,
    SUM(oi.price) AS total_merchandise_sales_value
FROM products p	   
JOIN order_items oi 
    ON p.product_id = oi.product_id
JOIN orders o
    ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY p.product_category_name
ORDER BY total_merchandise_sales_value DESC
LIMIT 10;

-- 20) Top 10 product categories by unique delivered orders
SELECT 
    p.product_category_name,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(oi.price) AS total_merchandise_sales_value
FROM products p	   
JOIN order_items oi 
    ON p.product_id = oi.product_id
JOIN orders o
    ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY p.product_category_name
ORDER BY total_orders DESC
LIMIT 10;

-- 21) Top 10 categories with average item spend per order
SELECT 
    p.product_category_name,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(oi.price) AS total_merchandise_sales_value,
    ROUND(SUM(oi.price) / COUNT(DISTINCT o.order_id), 2) AS avg_category_value_per_order
FROM products p	   
JOIN order_items oi 
    ON p.product_id = oi.product_id
JOIN orders o
    ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY p.product_category_name
ORDER BY total_orders DESC
LIMIT 10;

-- 22) Repeat customers with more than one delivered order
SELECT 
    c.customer_unique_id,
    COUNT(DISTINCT o.order_id) AS total_orders
FROM customers c
JOIN orders o 
    ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_unique_id
HAVING COUNT(DISTINCT o.order_id) > 1
ORDER BY total_orders DESC;

-- 23) Repeat customer percentage among delivered orders
WITH customer_orders AS (
    SELECT 
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS total_orders
    FROM customers c   
    JOIN orders o 
        ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT 
    COUNT(CASE WHEN total_orders > 1 THEN 1 END) AS repeat_customers_count,
    COUNT(*) AS total_delivered_customers,
    ROUND(
        100.0 * COUNT(CASE WHEN total_orders > 1 THEN 1 END) / COUNT(*), 
        2
    ) AS repeat_customer_percentage
FROM customer_orders;

-- 24) Top 10 customers by total payment value from delivered orders
SELECT 
    c.customer_unique_id,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(op.payment_value) AS total_payment_value
FROM customers c
JOIN orders o 
    ON c.customer_id = o.customer_id
JOIN order_payments op
    ON o.order_id = op.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_unique_id
ORDER BY total_payment_value DESC
LIMIT 10;

-- 25) Payment value contribution by customer state
SELECT 
    c.customer_state,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(op.payment_value) AS total_payment_value,
    ROUND(SUM(op.payment_value) / COUNT(DISTINCT o.order_id), 2) AS avg_payment_per_order
FROM customers c
JOIN orders o 
    ON c.customer_id = o.customer_id
JOIN order_payments op
    ON o.order_id = op.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY total_payment_value DESC;

-- 26) Average delivery duration in days (purchase to customer delivery)
SELECT ROUND(
    AVG(EXTRACT(EPOCH FROM (
        order_delivered_customer_date - order_purchase_timestamp
    )) / 86400.0)::numeric,
    2
) AS avg_delivery_days
FROM orders
WHERE order_purchase_timestamp IS NOT NULL
  AND order_delivered_customer_date IS NOT NULL
  AND order_delivered_customer_date >= order_purchase_timestamp
  AND order_status = 'delivered';

-- 27) On-time vs. late delivery counts and rates
SELECT 
    COUNT(*) AS orders_analyzed,
    SUM(CASE WHEN CAST(order_delivered_customer_date AS DATE) <= CAST(order_estimated_delivery_date AS DATE) THEN 1 ELSE 0 END) AS on_time_orders,
    SUM(CASE WHEN CAST(order_delivered_customer_date AS DATE) > CAST(order_estimated_delivery_date AS DATE) THEN 1 ELSE 0 END) AS late_orders,
    ROUND(100.00 * SUM(CASE WHEN CAST(order_delivered_customer_date AS DATE) <= CAST(order_estimated_delivery_date AS DATE) THEN 1 ELSE 0 END) / COUNT(*), 2) AS on_time_percentage,
    ROUND(100.00 * SUM(CASE WHEN CAST(order_delivered_customer_date AS DATE) > CAST(order_estimated_delivery_date AS DATE) THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_percentage
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_estimated_delivery_date IS NOT NULL
  AND order_purchase_timestamp IS NOT NULL
  AND order_delivered_customer_date >= order_purchase_timestamp;

-- 28) Late delivery rate by customer state (minimum 100 orders)
SELECT 
    c.customer_state,
    COUNT(*) AS orders_analyzed,
    SUM(CASE WHEN CAST(o.order_delivered_customer_date AS DATE) > CAST(o.order_estimated_delivery_date AS DATE) THEN 1 ELSE 0 END) AS late_orders,
    ROUND(100.00 * SUM(CASE WHEN CAST(o.order_delivered_customer_date AS DATE) > CAST(o.order_estimated_delivery_date AS DATE) THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_percentage
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_estimated_delivery_date IS NOT NULL
  AND o.order_purchase_timestamp IS NOT NULL
  AND o.order_delivered_customer_date >= o.order_purchase_timestamp
GROUP BY c.customer_state
HAVING COUNT(*) >= 100
ORDER BY late_percentage DESC;

-- 29) Average review score comparison: on-time vs. late deliveries
WITH valid_orders AS (
    SELECT 
        order_id,
        CASE 
            WHEN DATE(order_delivered_customer_date) <= DATE(order_estimated_delivery_date) THEN 'On time'
            ELSE 'Late'
        END AS delivery_group
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL
      AND order_purchase_timestamp IS NOT NULL
      AND order_delivered_customer_date >= order_purchase_timestamp
),
order_avg_reviews AS (
    SELECT 
        order_id,
        AVG(review_score) AS order_avg_score
    FROM order_reviews
    WHERE review_score IS NOT NULL
    GROUP BY order_id
)
SELECT 
    v.delivery_group,
    COUNT(r.order_id) AS reviewed_orders,
    ROUND(AVG(r.order_avg_score), 2) AS avg_review_score
FROM valid_orders v
JOIN order_avg_reviews r
    ON v.order_id = r.order_id
GROUP BY v.delivery_group
ORDER BY v.delivery_group DESC;

-- 30) Month-over-month payment growth with calendar-gap validation
WITH monthly_payments AS (
    SELECT 
        TO_CHAR(DATE_TRUNC('month', o.order_purchase_timestamp), 'YYYY-MM') AS purchase_month,
        DATE_TRUNC('month', o.order_purchase_timestamp)::DATE AS month_date,
        SUM(p.payment_value) AS total_payment_value
    FROM orders o
    JOIN order_payments p
        ON o.order_id = p.order_id
    WHERE o.order_purchase_timestamp IS NOT NULL
    GROUP BY 1, 2
),
monthly_with_lag AS (
    SELECT 
        purchase_month,
        month_date,
        total_payment_value,
        CASE 
            WHEN LAG(month_date) OVER (ORDER BY month_date) = month_date - INTERVAL '1 month'
            THEN LAG(total_payment_value) OVER (ORDER BY month_date)
            ELSE NULL 
        END AS previous_month_payment
    FROM monthly_payments
)
SELECT 
    purchase_month,
    ROUND(total_payment_value, 2) AS total_payment_value,
    ROUND(previous_month_payment, 2) AS previous_month_payment,
    CASE 
        WHEN previous_month_payment IS NULL OR previous_month_payment = 0 THEN NULL
        ELSE ROUND(((total_payment_value - previous_month_payment) / previous_month_payment) * 100.0, 2)
    END AS mom_growth_percentage
FROM monthly_with_lag
ORDER BY month_date ASC;