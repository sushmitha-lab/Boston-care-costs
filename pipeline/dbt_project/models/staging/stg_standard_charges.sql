-- Staging: read the pipeline's Parquet output directly (DuckDB native).
select
    hospital_id,
    hospital_name,
    try_cast(last_updated_on as date)          as last_updated_on,
    mrf_version,
    description,
    setting,
    coalesce(
        case when code_1_type in ('CPT','HCPCS','MS-DRG','DRG','APR-DRG') then code_1 end,
        case when code_2_type in ('CPT','HCPCS','MS-DRG','DRG','APR-DRG') then code_2 end
    )                                          as billing_code,
    coalesce(
        case when code_1_type in ('CPT','HCPCS','MS-DRG','DRG','APR-DRG') then code_1_type end,
        case when code_2_type in ('CPT','HCPCS','MS-DRG','DRG','APR-DRG') then code_2_type end
    )                                          as billing_code_type,
    gross_charge,
    discounted_cash,
    payer_name,
    plan_name,
    negotiated_dollar,
    min_charge,
    max_charge,
    methodology
from read_parquet('../../data/staging/standard_charges.parquet')
