WITH event_map_cte AS (
    -- 1. 코드 매핑을 딕셔너리(Map) 형태로 선언
    -- 0~12에 해당하는 실제 eventCode 값을 배열 순서에 맞게 기입하세요.
    SELECT MAP(
        ARRAY['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
        ARRAY['AA', 'BB', 'CC', 'DD', 'EE', 'FF', 'GG', 'HH', 'II', 'JJ', 'KK', 'LL', 'MM'] 
    ) AS code_map
),
valid_spec AS (
    -- 2. Spec 데이터 필터링 및 파이프(|) 구분자 문자열을 배열로 변환
    SELECT 
        fab_id, 
        lot_cd, 
        oper_id, 
        prmt_nm, 
        oper_event,
        split(oper_event, '|') AS oper_event_array
    FROM spec_table
    WHERE oper_event IS NOT NULL 
      AND oper_event != 'N'
),
history_data AS (
    -- 3. History 데이터 추출 및 파라미터 배열화
    SELECT 
        fab_id, lot_cd, oper_id, title AS event_desc, event_tm, event_cd, step_id,
        CAST(json_extract(param_val_json, '$.PARAM') AS ARRAY(VARCHAR)) AS ITEMS
    FROM hive.tas.his
    WHERE event_tm BETWEEN date_parse('${fromStr}', '%Y%m%d%H%i%s') 
                       AND date_parse('${nowStr}', '%Y%m%d%H%i%s')
)
-- 4. Spec과 History 조인 및 집계
SELECT 
    s.fab_id, 
    s.lot_cd, 
    s.oper_id, 
    s.prmt_nm, 
    s.oper_event,
    array_agg(h.event_desc ORDER BY h.event_tm) AS event_desc_list,
    array_agg(h.event_tm ORDER BY h.event_tm) AS event_tm_list
FROM valid_spec s
JOIN history_data h
  ON s.fab_id = h.fab_id
 AND s.lot_cd = h.lot_cd
 AND s.oper_id = h.oper_id
CROSS JOIN event_map_cte m  -- Map 테이블을 1회 Cross Join하여 환경 변수처럼 사용
WHERE 1=1
  -- [조건 A] 이벤트 코드 검사 로직
  AND (
      contains(s.oper_event_array, '-1') 
      OR contains(
          -- s.oper_event_array(예: ['1','3'])의 각 요소를 m.code_map을 참조해 ['BB','DD'] 로 변환
          transform(s.oper_event_array, x -> element_at(m.code_map, x)), 
          h.event_cd
      )
  )
  -- [조건 B] 파라미터 포함 여부 검사 (any_match)
  AND (
      h.step_id = '*'
      OR any_match(h.ITEMS, item -> 
          item LIKE '%' || s.prmt_nm || ',%' 
          OR item LIKE '%,' || s.prmt_nm || '%' 
          OR item = s.prmt_nm
      )
  )
GROUP BY 
    s.fab_id, s.lot_cd, s.oper_id, s.prmt_nm, s.oper_event
