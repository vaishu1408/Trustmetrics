select
    id as order_item_id,
    order_id,
    user_id,
    product_id,
    status,
    sale_price,
    created_at,
    shipped_at,
    delivered_at,
    returned_at
from `bigquery-public-data.thelook_ecommerce.order_items`