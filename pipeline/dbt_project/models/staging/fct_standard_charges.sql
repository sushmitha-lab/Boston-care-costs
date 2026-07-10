select
    s.hospital_id,
    d.service_key,
    s.setting,
    s.payer_name,
    s.plan_name,
    s.gross_charge,
    s.discounted_cash,
    s.negotiated_dollar,
    s.min_charge,
    s.max_charge,
    s.methodology
from {{ ref('stg_standard_charges') }} s
join {{ ref('dim_service') }} d
  on d.billing_code = s.billing_code
 and d.billing_code_type = s.billing_code_type
