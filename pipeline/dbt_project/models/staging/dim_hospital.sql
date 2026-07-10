select distinct
    hospital_id,
    hospital_name,
    mrf_version,
    max(last_updated_on) over (partition by hospital_id) as mrf_last_updated
from {{ ref('stg_standard_charges') }}
