select
    oi.order_item_id,
    oi.order_id,
    oi.user_id,
    oi.product_id,
    oi.status,
    oi.sale_price,
    p.cost,
    oi.sale_price - p.cost as item_margin,
    date(oi.created_at) as order_date,
    oi.status != 'Cancelled' as is_gross,
    oi.status not in ('Cancelled', 'Returned') as is_net
from {{ ref('stg_order_items') }} oi
left join {{ ref('stg_products') }} p using (product_id)