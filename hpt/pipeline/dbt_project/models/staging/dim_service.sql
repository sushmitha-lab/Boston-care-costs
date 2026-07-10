-- One row per billable service (code + type), canonical description =
-- most common description across hospitals.
with ranked as (
    select
        billing_code,
        billing_code_type,
        description,
        setting,
        count(*) as n,
        row_number() over (
            partition by billing_code, billing_code_type
            order by count(*) desc
        ) as rn
    from {{ ref('stg_standard_charges') }}
    where billing_code is not null
    group by 1, 2, 3, 4
)
select
    billing_code || '-' || billing_code_type as service_key,
    billing_code,
    billing_code_type,
    description as canonical_description,
    setting
from ranked
where rn = 1
