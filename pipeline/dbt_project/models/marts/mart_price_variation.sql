-- Analyst-layer finding: how much does the same service vary across
-- hospitals? spread_ratio = max cash price / min cash price.
select
    service_key,
    any_value(billing_code)           as billing_code,
    any_value(canonical_description)  as canonical_description,
    any_value(setting)                as setting,
    count(distinct hospital_id)       as n_hospitals,
    min(cash_price)                   as min_cash_price,
    max(cash_price)                   as max_cash_price,
    round(max(cash_price) / nullif(min(cash_price), 0), 2) as spread_ratio,
    round(max(cash_price) - min(cash_price), 2)            as absolute_spread
from {{ ref('mart_cash_price_comparison') }}
where cash_price is not null
group by service_key
having count(distinct hospital_id) >= 2
order by spread_ratio desc
