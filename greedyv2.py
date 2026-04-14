import pygame
import random
import sys

# 초기 설정
WIDTH, HEIGHT = 1100, 800
FPS = 60
DATA_COUNT = 50
PARTITION_COUNT = 10
CANVAS_HEIGHT = 700 # 바닥 기준선

# 색상
WHITE = (255, 255, 255)
GRAY = (220, 220, 220)
DARK_GRAY = (80, 80, 80)
BLUE = (74, 144, 226)
ORANGE = (245, 166, 35)
BLACK = (30, 30, 30)

class DataUnit:
    def __init__(self, size, x, y, width):
        self.size = size  # 데이터 크기 (예: 1~100MB)
        self.height = max(2, int(size * 1.5))  # 크기에 비례한 두께 (최소 2픽셀)
        self.rect = pygame.Rect(x, y - self.height, width, self.height)
        self.target_pos = None
        self.is_moving = False
        self.speed = 20

    def move(self):
        if self.is_moving and self.target_pos:
            dx = self.target_pos[0] - self.rect.x
            dy = self.target_pos[1] - self.rect.y
            dist = (dx**2 + dy**2)**0.5
            
            if dist < self.speed:
                self.rect.x, self.rect.y = self.target_pos
                self.is_moving = False
            else:
                self.rect.x += int(self.speed * dx / dist)
                self.rect.y += int(self.speed * dy / dist)

def run_simulation():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Greedy Data Skew Management Simulation")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("malgungothic", 16)

    # 데이터 생성 (1~100 사이의 크기)
    raw_data_sizes = [random.randint(5, 100) for _ in range(DATA_COUNT)]
    partitions = [[] for _ in range(PARTITION_COUNT)]
    partition_total_heights = [0] * PARTITION_COUNT
    
    units = []
    def reset_units():
        units.clear()
        current_y = CANVAS_HEIGHT - 20
        for size in raw_data_sizes:
            unit = DataUnit(size, 150, current_y, 80)
            units.append(unit)
            current_y -= (unit.height + 2) # 데이터 사이 간격 2px

    reset_units()
    
    active_unit = None
    started = False
    sorted_mode = False

    while True:
        screen.fill(WHITE)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s:
                    started = True
                if event.key == pygame.K_r:
                    raw_data_sizes.sort(reverse=True)
                    reset_units()
                    sorted_mode = True

        # 1. 왼쪽 원기둥 (Source) UI
        pygame.draw.ellipse(screen, DARK_GRAY, (130, 50, 120, 30), 2)
        pygame.draw.line(screen, DARK_GRAY, (130, 65), (130, CANVAS_HEIGHT - 10), 3)
        pygame.draw.line(screen, DARK_GRAY, (250, 65), (250, CANVAS_HEIGHT - 10), 3)
        pygame.draw.arc(screen, DARK_GRAY, (130, CANVAS_HEIGHT - 25, 120, 30), 3.14, 0, 3)

        # 2. 오른쪽 파티션 (Target) UI
        for i in range(PARTITION_COUNT):
            x_pos = 400 + (i * 65)
            # 파티션 가이드 라인
            pygame.draw.rect(screen, GRAY, (x_pos, 200, 55, CANVAS_HEIGHT - 200), 1)
            label = font.render(f"P{i}", True, BLACK)
            screen.blit(label, (x_pos + 15, CANVAS_HEIGHT + 5))
            # 현재 쌓인 높이 텍스트
            h_text = font.render(f"{partition_total_heights[i]}", True, BLUE)
            screen.blit(h_text, (x_pos + 10, CANVAS_HEIGHT - partition_total_heights[i] - 220))

        # 3. Greedy 분산 로직
        if started and not active_unit and units:
            active_unit = units.pop()
            
            # Greedy: 현재까지 쌓인 두께(height)의 합이 가장 적은 파티션 선택
            target_idx = partition_total_heights.index(min(partition_total_heights))
            
            target_x = 400 + (target_idx * 65) + 5
            # 파티션 바닥에서부터 쌓아 올림
            target_y = (CANVAS_HEIGHT - 10) - partition_total_heights[target_idx] - active_unit.height
            
            active_unit.target_pos = (target_x, target_y)
            active_unit.is_moving = True
            active_unit.rect.width = 45

        # 4. 렌더링
        for u in units:
            pygame.draw.rect(screen, ORANGE, u.rect)
            pygame.draw.rect(screen, BLACK, u.rect, 1) # 테두리

        for p_list in partitions:
            for p_unit in p_list:
                pygame.draw.rect(screen, BLUE, p_unit.rect)
                pygame.draw.rect(screen, WHITE, p_unit.rect, 1)

        if active_unit:
            active_unit.move()
            pygame.draw.rect(screen, BLUE, active_unit.rect)
            if not active_unit.is_moving:
                idx = (active_unit.rect.x - 405) // 65
                partitions[idx].append(active_unit)
                # 실제 데이터의 크기(두께)만큼 파티션 높이 누적
                partition_total_heights[idx] += active_unit.height
                active_unit = None

        # 가이드 및 상태 정보
        title = font.render(f"Greedy Load Balancing (Data Size Awareness)", True, BLACK)
        screen.blit(title, (20, 20))
        msg = "S: 시작 | R: 내림차순 정렬 (LPT 알고리즘 효과 확인) | 정렬: " + ("ON" if sorted_mode else "OFF")
        guide = font.render(msg, True, DARK_GRAY)
        screen.blit(guide, (20, 50))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    run_simulation()
