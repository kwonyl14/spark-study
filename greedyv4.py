import pygame
import random
import sys

# 초기 설정
WIDTH, HEIGHT = 1100, 800
FPS = 60
DATA_COUNT = 50
PARTITION_COUNT = 10
CANVAS_HEIGHT = 700 
# 요구사항 반영: 원기둥 표시 높이를 기존의 80% 수준으로 제한 (시각적 가이드)
SOURCE_CYLINDER_HEIGHT = int((CANVAS_HEIGHT - 65) * 0.8) 

# 색상
WHITE = (255, 255, 255)
GRAY = (220, 220, 220)
DARK_GRAY = (80, 80, 80)
BLUE = (74, 144, 226)
ORANGE = (245, 166, 35)
BLACK = (30, 30, 30)

class DataUnit:
    def __init__(self, size, x, y, width):
        self.size = size
        # 데이터 크기가 커짐에 따라 렌더링 두께 비율을 살짝 조정 (0.15 -> 0.18)
        self.height = max(1, int(size * 0.18))  
        self.rect = pygame.Rect(x, y - self.height, width, self.height)
        self.target_pos = None
        self.is_moving = False
        self.speed = 28 # 거대 데이터 이동을 위해 속도를 조금 더 올림

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
    pygame.display.set_caption("Extreme Data Skew & Greedy Balancing")
    clock = pygame.time.Clock()
    
    try:
        font = pygame.font.SysFont("malgungothic", 16)
        bold_font = pygame.font.SysFont("malgungothic", 19, bold=True)
    except:
        font = pygame.font.SysFont("arial", 16)
        bold_font = pygame.font.SysFont("arial", 19, bold=True)

    # 요구사항 반영: 극단적인 데이터 구성
    def generate_skewed_data():
        data = [100, 95] # 거대 데이터 2개
        # 나머지 48개는 1~70MB 사이 램덤
        data.extend([random.randint(1, 70) for _ in range(DATA_COUNT - 2)])
        return data

    raw_data_sizes = generate_skewed_data()
    partitions = [[] for _ in range(PARTITION_COUNT)]
    partition_total_heights = [0] * PARTITION_COUNT
    
    units = []
    def reset_units(is_sorted=False):
        units.clear()
        # LPT: 큰 데이터가 리스트 끝(원기둥 위)에 오게 오름차순 정렬
        display_sizes = sorted(raw_data_sizes) if is_sorted else raw_data_sizes
        
        current_y = CANVAS_HEIGHT - 20
        for size in display_sizes:
            unit = DataUnit(size, 150, current_y, 80)
            units.append(unit)
            current_y -= (unit.height + 1)

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
                    sorted_mode = True
                    reset_units(is_sorted=True)
                if event.key == pygame.K_ESCAPE:
                    started = False
                    sorted_mode = False
                    raw_data_sizes = generate_skewed_data()
                    partitions = [[] for _ in range(PARTITION_COUNT)]
                    partition_total_heights = [0] * PARTITION_COUNT
                    reset_units()

        # 1. 왼쪽 원기둥 UI (높이 조정 반영)
        cylinder_top_y = CANVAS_HEIGHT - SOURCE_CYLINDER_HEIGHT - 20
        pygame.draw.ellipse(screen, DARK_GRAY, (130, cylinder_top_y - 15, 120, 30), 2)
        pygame.draw.line(screen, DARK_GRAY, (130, cylinder_top_y), (130, CANVAS_HEIGHT - 10), 3)
        pygame.draw.line(screen, DARK_GRAY, (250, cylinder_top_y), (250, CANVAS_HEIGHT - 10), 3)
        pygame.draw.arc(screen, DARK_GRAY, (130, CANVAS_HEIGHT - 25, 120, 30), 3.14, 0, 3)

        # 2. 오른쪽 파티션 UI
        for i in range(PARTITION_COUNT):
            x_pos = 400 + (i * 65)
            pygame.draw.rect(screen, GRAY, (x_pos, 150, 55, CANVAS_HEIGHT - 150), 1)
            label = font.render(f"P{i}", True, BLACK)
            screen.blit(label, (x_pos + 15, CANVAS_HEIGHT + 5))
            
            h_val = partition_total_heights[i]
            # 거대 데이터 파티션 강조 (MB 단위로 표시)
            is_skewed = any(u.size >= 95 for u in partitions[i])
            h_text_color = ORANGE if is_skewed else BLUE
            
            h_text = bold_font.render(f"{h_val}", True, h_text_color)
            text_y = CANVAS_HEIGHT - h_val - 30 if h_val < 500 else 160
            screen.blit(h_text, (x_pos + 10, text_y))

        # 3. Greedy 로직 (가장 낮은 파티션 찾기)
        if started and not active_unit and units:
            active_unit = units.pop()
            target_idx = partition_total_heights.index(min(partition_total_heights))
            
            target_x = 400 + (target_idx * 65) + 5
            target_y = (CANVAS_HEIGHT - 10) - partition_total_heights[target_idx] - active_unit.height
            
            active_unit.target_pos = (target_x, target_y)
            active_unit.is_moving = True
            active_unit.rect.width = 45

        # 4. 유닛 렌더링
        for u in units:
            pygame.draw.rect(screen, ORANGE if u.size >= 95 else ORANGE, u.rect)
            if u.height > 2: pygame.draw.rect(screen, BLACK, u.rect, 1)

        for p_list in partitions:
            for p_unit in p_list:
                pygame.draw.rect(screen, BLUE, p_unit.rect)
                if p_unit.height > 2: pygame.draw.rect(screen, WHITE, p_unit.rect, 1)

        if active_unit:
            active_unit.move()
            pygame.draw.rect(screen, BLUE, active_unit.rect)
            if not active_unit.is_moving:
                idx = (active_unit.rect.x - 405) // 65
                partitions[idx].append(active_unit)
                partition_total_heights[idx] += active_unit.height
                active_unit = None

        # 상태 정보 표시
        title = font.render(f"Extreme Skew Handling (Large: 100, 95 MB)", True, BLACK)
        screen.blit(title, (20, 20))
        msg = "S: 시작 | R: 큰 데이터 우선(LPT) | ESC: 데이터 재생성 | 정렬: " + ("ON" if sorted_mode else "OFF")
        guide = font.render(msg, True, DARK_GRAY)
        screen.blit(guide, (20, 50))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    run_simulation()
