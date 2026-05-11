WITH valid_spec AS (
    SELECT 
        fab_id, lot_cd, oper_id, prmt_nm, oper_event,
        split(oper_event, '|') AS oper_event_array
    FROM spec_table
    WHERE oper_event IS NOT NULL AND oper_event != 'N'
),
event_map_cte AS (
    SELECT MAP(
        ARRAY['0','1','2','3','4','5','6','7','8','9','10','11','12'],
        ARRAY['AA','BB','CC','DD','EE','FF','GG','HH','II','JJ','KK','LL','MM']
    ) AS code_map
),
matched_his AS (
    -- 0~8 (AA~II) 담당
    SELECT 
        s.fab_id, s.lot_cd, s.oper_id, s.prmt_nm, s.oper_event,
        h.title AS event_desc, h.event_tm
    FROM valid_spec s
    JOIN hive.tas.his h
      ON s.fab_id = h.fab_id AND s.lot_cd = h.lot_cd AND s.oper_id = h.oper_id
    CROSS JOIN event_map_cte m
    WHERE 1=1
      AND h.event_tm BETWEEN date_parse('${fromStr}', '%Y%m%d%H%i%s') AND date_parse('${nowStr}', '%Y%m%d%H%i%s')
      -- [수정된 코드 필터링 로직]
      AND contains(
          transform(
              -- -1이 있으면 0~8 전체를, 없으면 0~8 중 입력된 값만 추출
              IF(contains(s.oper_event_array, '-1'), 
                 ARRAY['0','1','2','3','4','5','6','7','8'], 
                 array_intersect(s.oper_event_array, ARRAY['0','1','2','3','4','5','6','7','8'])),
              x -> element_at(m.code_map, x)
          ),
          h.event_cd
      )
      AND (h.step_id = '*' OR any_match(CAST(json_extract(h.param_val_json, '$.PARAM') AS ARRAY(VARCHAR)), 
                                        item -> item LIKE '%' || s.prmt_nm || ',%' OR item LIKE '%,' || s.prmt_nm || '%' OR item = s.prmt_nm))
),
matched_issue AS (
    -- 9~12 (JJ~MM) 담당
    SELECT 
        s.fab_id, s.lot_cd, s.oper_id, s.prmt_nm, s.oper_event,
        i.eqp_id AS event_desc, i.issue_tm AS event_tm
    FROM valid_spec s
    JOIN hive.tas.issue i
      ON s.fab_id = i.fab_id AND s.lot_cd = i.lot_cd AND s.oper_id = i.oper_id AND s.prmt_nm = i.param_nm 
    CROSS JOIN event_map_cte m
    WHERE 1=1
      AND i.issue_tm BETWEEN date_parse('${fromStr}', '%Y%m%d%H%i%s') AND date_parse('${nowStr}', '%Y%m%d%H%i%s')
      -- [수정된 코드 필터링 로직]
      AND (
          i.hot_yn = 'Y' -- HOT_YN은 별도 조건으로 유지
          OR contains(
              transform(
                  -- -1이 있으면 9~12 전체를, 없으면 9~12 중 입력된 값만 추출
                  IF(contains(s.oper_event_array, '-1'), 
                     ARRAY['9','10','11','12'], 
                     array_intersect(s.oper_event_array, ARRAY['9','10','11','12'])),
                  x -> element_at(m.code_map, x)
              ),
              i.issue_grade_typ
          )
      )
),
union_results AS (
    SELECT * FROM matched_his UNION ALL SELECT * FROM matched_issue
)
SELECT 
    fab_id, lot_cd, oper_id, prmt_nm, oper_event,
    array_join(array_agg(event_desc ORDER BY event_tm), '|') AS event_desc_list,
    array_join(transform(array_agg(event_tm ORDER BY event_tm), x -> CAST(x AS VARCHAR)), '|') AS event_tm_list
FROM union_results
GROUP BY fab_id, lot_cd, oper_id, prmt_nm, oper_event
