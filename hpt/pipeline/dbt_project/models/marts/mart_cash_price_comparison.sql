-- The app's core dataset: one row per service per hospital, cash price
-- plus negotiated-rate distribution.
with per_hospital as (
    select
        f.service_key,
        f.hospital_id,
        max(f.gross_charge)                          as gross_charge,
        max(f.discounted_cash)                       as cash_price,
        min(f.negotiated_dollar)                     as min_negotiated,
        max(f.negotiated_dollar)                     as max_negotiated,
        median(f.negotiated_dollar)                  as median_negotiated,
        count(distinct f.payer_name)                 as n_payers
    from {{ ref('fct_standard_charges') }} f
    group by 1, 2
)
select
    d.service_key,
    d.billing_code,
    d.billing_code_type,
    d.canonical_description,
    d.setting,
    h.hospital_name,
    p.*  exclude (service_key, hospital_id),
    p.hospital_id
from per_hospital p
join {{ ref('dim_service') }}  d on d.service_key = p.service_key
join {{ ref('dim_hospital') }} h on h.hospital_id = p.hospital_id
