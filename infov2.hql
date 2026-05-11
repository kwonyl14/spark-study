WITH valid_spec AS (
    -- 1. Spec 데이터 필터링 및 배열 변환
    SELECT 
        fab_id, lot_cd, oper_id, prmt_nm, oper_event,
        split(oper_event, '|') AS oper_event_array
    FROM spec_table
    WHERE oper_event IS NOT NULL AND oper_event != 'N'
),
event_map_cte AS (
    -- 2. 전체 이벤트 코드 매핑 (0~12 전체 정의)
    SELECT MAP(
        ARRAY['0','1','2','3','4','5','6','7','8','9','10','11','12'],
        ARRAY['AA','BB','CC','DD','EE','FF','GG','HH','II','JJ','KK','LL','MM']
    ) AS code_map
),
matched_his AS (
    -- 3. [his 테이블 조인] 0~8 코드가 있거나 -1인 경우만 수행
    SELECT 
        s.fab_id, s.lot_cd, s.oper_id, s.prmt_nm, s.oper_event,
        h.title AS event_desc, h.event_tm
    FROM valid_spec s
    JOIN hive.tas.his h
      ON s.fab_id = h.fab_id AND s.lot_cd = h.lot_cd AND s.oper_id = h.oper_id
    CROSS JOIN event_map_cte m
    WHERE 1=1
      -- [분기 조건] oper_event_array에 -1이 있거나, 0~8의 교집합이 존재하는 경우에만 이 블록 실행
      AND (
          contains(s.oper_event_array, '-1') 
          OR cardinality(array_intersect(s.oper_event_array, ARRAY['0','1','2','3','4','5','6','7','8'])) > 0
      )
      AND h.event_tm BETWEEN date_parse('${fromStr}', '%Y%m%d%H%i%s') AND date_parse('${nowStr}', '%Y%m%d%H%i%s')
      -- [코드 검증] -1 이거나 매핑된 event_cd가 일치하는 경우
      AND (
          contains(s.oper_event_array, '-1')
          OR contains(transform(s.oper_event_array, x -> element_at(m.code_map, x)), h.event_cd)
      )
      -- [파라미터 검증] JSON 추출 후 검사
      AND (
          h.step_id = '*'
          OR any_match(CAST(json_extract(h.param_val_json, '$.PARAM') AS ARRAY(VARCHAR)), 
                       item -> item LIKE '%' || s.prmt_nm || ',%' OR item LIKE '%,' || s.prmt_nm || '%' OR item = s.prmt_nm)
      )
),
matched_issue AS (
    -- 4. [issue 테이블 조인] 9~12 코드가 있거나 -1인 경우만 수행
    SELECT 
        s.fab_id, s.lot_cd, s.oper_id, s.prmt_nm, s.oper_event,
        i.eqp_id AS event_desc, i.issue_tm AS event_tm
    FROM valid_spec s
    JOIN hive.tas.issue i
      ON s.fab_id = i.fab_id AND s.lot_cd = i.lot_cd AND s.oper_id = i.oper_id
      -- issue 테이블은 param_nm 컬럼이 존재하므로 직접 조인
      AND s.prmt_nm = i.param_nm 
    CROSS JOIN event_map_cte m
    WHERE 1=1
      -- [분기 조건] oper_event_array에 -1이 있거나, 9~12의 교집합이 존재하는 경우에만 이 블록 실행
      AND (
          contains(s.oper_event_array, '-1') 
          OR cardinality(array_intersect(s.oper_event_array, ARRAY['9','10','11','12'])) > 0
      )
      AND i.issue_tm BETWEEN date_parse('${fromStr}', '%Y%m%d%H%i%s') AND date_parse('${nowStr}', '%Y%m%d%H%i%s')
      -- [코드 검증] HOT_YN = 'Y' 이거나, -1 이거나, 매핑된 issue_grade_typ가 일치하는 경우
      AND (
          i.hot_yn = 'Y'
          OR contains(s.oper_event_array, '-1')
          OR contains(transform(s.oper_event_array, x -> element_at(m.code_map, x)), i.issue_grade_typ)
      )
),
union_results AS (
    -- 5. 양쪽 테이블에서 매칭된 결과셋 병합
    SELECT * FROM matched_his
    UNION ALL
    SELECT * FROM matched_issue
)
-- 6. 최종 집계 (결과가 있는 로우만 '|' 구분자로 합침)
SELECT 
    fab_id, 
    lot_cd, 
    oper_id, 
    prmt_nm, 
    oper_event,
    array_join(array_agg(event_desc ORDER BY event_tm), '|') AS event_desc_list,
    array_join(transform(array_agg(event_tm ORDER BY event_tm), x -> CAST(x AS VARCHAR)), '|') AS event_tm_list
FROM union_results
GROUP BY 
    fab_id, lot_cd, oper_id, prmt_nm, oper_event
