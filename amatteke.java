package com.example.parser;

import com.example.parser.SvdLogParser.SvdParseResult;
import org.junit.Test;
import static org.junit.Assert.*;

public class SvdLogParserTest {

    @Test
    public void testProcessSuccess_정상_케이스_파싱_및_데이터_검증() {
        // Given
        String filename = "2026-06-24_14-07-51_1306195NADT44_04_NA_SLIM2_R01_M15_C2_Step10.svd";

        // When
        SvdParseResult result = SvdLogParser.parse(filename);

        // Then
        assertNotNull(result);
        assertEquals("Process", result.category);
        assertEquals("2026-06-24", result.date);
        assertEquals("14-07-51", result.time);
        assertEquals("130619", result.lotNumber); // 앞 6자리 숫자
        assertEquals("5NADT44", result.lotId);    // 나머지 문자열
        assertEquals("04", result.slotId);
        assertEquals("NA_SLIM2_R01_M15_C2", result.recipeId); // 언더바 다수 포함 검증
        assertEquals("10", result.stepId);
    }

    @Test
    public void testCleanSuccess_slotId가_00인_경우() {
        // Given & When
        SvdParseResult result = SvdLogParser.parse("2026-06-24_14-07-51__00_ICC_SLIM2_R01_M15_C2_Step10.svd");

        // Then
        assertEquals("Clean", result.category);
        assertEquals("", result.lotNumber);
        assertEquals("", result.lotId);
        assertEquals("00", result.slotId);
        assertEquals("ICC_SLIM2_R01_M15_C2", result.recipeId);
    }

    @Test
    public void testCleanSuccess_slotId가_빈값인_경우() {
        // Given & When
        SvdParseResult result = SvdLogParser.parse("2026-06-24_14-07-51___ICC_SLIM2_R01_M15_C2_Step10.svd");

        // Then
        assertEquals("Clean", result.category);
        assertEquals("", result.slotId); // ___ 연속 언더바로 인한 빈 문자열 매칭 확인
        assertEquals("ICC_SLIM2_R01_M15_C2", result.recipeId);
    }

    @Test
    public void testCleanSuccess_키워드_위치별_검증() {
        // recipeId 중간에 ICC가 있는 경우
        SvdParseResult result1 = SvdLogParser.parse("2026-06-24_14-07-51__00_SLIM2_ICC_R01_Step10.svd");
        assertEquals("Clean", result1.category);
        assertEquals("SLIM2_ICC_R01", result1.recipeId);

        // recipeId에 PRE가 포함된 경우
        SvdParseResult result2 = SvdLogParser.parse("2026-06-24_14-07-51___SLIM2_PRE_R01_Step10.svd");
        assertEquals("Clean", result2.category);
        assertEquals("SLIM2_PRE_R01", result2.recipeId);
    }

    @Test
    public void testProcessValidationError_필수값이_비어있으면_예외발생() {
        // 1. Process인데 lotInfo가 비어있는 경우 (___로 시작)
        try {
            SvdLogParser.parse("2026-06-24_14-07-51___04_SLIM2_Step10.svd");
            fail("IllegalArgumentException이 발생해야 합니다.");
        } catch (IllegalArgumentException ex) {
            assertTrue(ex.getMessage().contains("lotId 칸이 비어있을 수 없습니다"));
        }

        // 2. Process인데 slotId가 비어있는 경우
        try {
            SvdLogParser.parse("2026-06-24_14-07-51_1306195NADT44__SLIM2_Step10.svd");
            fail("IllegalArgumentException이 발생해야 합니다.");
        } catch (IllegalArgumentException ex) {
            assertTrue(ex.getMessage().contains("slotId 칸이 비어있을 수 없습니다"));
        }
    }

    @Test
    public void testCleanValidationError_제약조건_위반시_예외발생() {
        // 1. Clean인데 lotInfo가 비어있지 않고 값이 들어온 경우
        try {
            SvdLogParser.parse("2026-06-24_14-07-51_1306195NADT44_00_ICC_SLIM2_Step10.svd");
            fail("IllegalArgumentException이 발생해야 합니다.");
        } catch (IllegalArgumentException ex) {
            assertTrue(ex.getMessage().contains("lotId 칸이 비어있어야 합니다"));
        }

        // 2. Clean인데 slotId에 '00'이나 빈값이 아닌 다른 숫자('04')가 들어온 경우
        try {
            SvdLogParser.parse("2026-06-24_14-07-51__04_ICC_SLIM2_Step10.svd");
            fail("IllegalArgumentException이 발생해야 합니다.");
        } catch (IllegalArgumentException ex) {
            assertTrue(ex.getMessage().contains("slotId는 빈 값이거나 '00'이어야 합니다"));
        }
    }

    @Test
    public void testRegexPatternMismatches_정규식_포맷_불일치_검증() {
        String[] invalidFilenames = {
            "20260624_14-07-51_1306195NADT44_04_NA_Step10.svd",       // 날짜 하이픈 누락
            "2026-06-24_14:07:51_1306195NADT44_04_NA_Step10.svd",       // 시간 콜론 사용
            "2026-06-24_14-07-51_1306195NADT44_04_NA_Step1.svd",        // StepId 1자리 에러
            "2026-06-24_14-07-51_1306195NADT44_04_NA_Step10f.svd",      // StepId 숫자가 아님
            "2026-06-24_14-07-51_1306195NADT44_04_NA_Step10.txt",       // 확장자 에러 (.txt)
            "2026-06-24_14-07-51_1306195NADT44_04_NA_Step10.svd.bak"    // 확장자 뒤 오염 문자열
        };

        for (String invalidFilename : invalidFilenames) {
            try {
                SvdLogParser.parse(invalidFilename);
                fail("정규식 패턴 불일치로 예외가 발생해야 합니다. 대상 파일명: " + invalidFilename);
            } catch (IllegalArgumentException ex) {
                assertEquals("정해진 파일명 포맷 패턴과 일치하지 않습니다.", ex.getMessage());
            }
        }
    }

    @Test
    public void testLotInfoLengthError_Lot_정보가_6자리_미만일때_예외발생() {
        // lotInfo 자리에 '123'만 들어와서 6자리 미만인 경우
        try {
            SvdLogParser.parse("2026-06-24_14-07-51_123_04_SLIM2_Step10.svd");
            fail("IllegalArgumentException이 발생해야 합니다.");
        } catch (IllegalArgumentException ex) {
            assertTrue(ex.getMessage().contains("최소 6자리 숫자 필요"));
        }
    }
}
