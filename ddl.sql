CREATE TABLE iceberg.sep.oes_summary_inf (
    -- Business Key
    fab                 STRING,
    eqp                 STRING,
    lot_id              STRING,
    slot_id             STRING,
    chamber             STRING,
    recipe              STRING,
    step_id             STRING,

    -- Wave Length Group
    wl_group            INT,
    wl_group_cnt        BIGINT,

    -- Summary Result
    avg_value_array     ARRAY<DOUBLE>,
    value_std           DOUBLE,
    value_min           DOUBLE,
    value_max           DOUBLE,
    value_mean          DOUBLE,
    value_median        DOUBLE,

    -- Source / Status
    source_file_key     STRING,
    summary_status      STRING,

    -- Partition
    dt                  DATE
)
USING iceberg
PARTITIONED BY (dt, fab);
