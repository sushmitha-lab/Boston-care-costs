-- Where is paying cash CHEAPER than the median negotiated insurance rate?
select
    service_key,
    billing_code,
    canonical_description,
    hospital_name,
    cash_price,
    median_negotiated,
    round(cash_price - median_negotiated, 2) as cash_minus_median_negotiated,
    cash_price < median_negotiated           as cash_beats_insurance
from {{ ref('mart_cash_price_comparison') }}
where cash_price is not null
  and median_negotiated is not null
order by cash_minus_median_negotiated
