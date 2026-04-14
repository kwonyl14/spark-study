import pygame
import random
import sys

# 초기 설정
WIDTH, HEIGHT = 1100, 800
FPS = 60
DATA_COUNT = 50
PARTITION_COUNT = 10
CANVAS_HEIGHT = 700 

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
        self.height = max(1, int(size * 0.15))  
        self.rect = pygame.Rect(x, y - self.height, width, self.height)
        self.target_pos = None
        self.is_moving = False
        self.speed = 25

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
    pygame.display.set_caption("Greedy Data Skew Management - LPT Order")
    clock = pygame.time.Clock()
    
    try:
        font = pygame.font.SysFont("malgungothic", 16)
    except:
        font = pygame.font.SysFont("arial", 16)

    raw_data_sizes = [random.randint(5, 100) for _ in range(DATA_COUNT)]
    partitions = [[] for _ in range(PARTITION_COUNT)]
    partition_total_heights = [0] * PARTITION_COUNT
    
    units = []
    def reset_units(is_sorted=False):
        units.clear()
        # 정렬 모드일 때: 큰 데이터가 리스트의 뒤로 가게 하여 pop()할 때 가장 큰 게 먼저 나오게 함
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
                    # R을 누르면 정렬 모드 활성화 및 데이터 재배치
                    sorted_mode = True
                    reset_units(is_sorted=True)
                if event.key == pygame.K_ESCAPE:
                    started = False
                    sorted_mode = False
                    raw_data_sizes = [random.randint(5, 100) for _ in range(DATA_COUNT)]
                    partitions = [[] for _ in range(PARTITION_COUNT)]
                    partition_total_heights = [0] * PARTITION_COUNT
                    reset_units()

        # UI 렌더링 (원기둥 및 파티션)
        pygame.draw.ellipse(screen, DARK_GRAY, (130, 50, 120, 30), 2)
        pygame.draw.line(screen, DARK_GRAY, (130, 65), (130, CANVAS_HEIGHT - 10), 3)
        pygame.draw.line(screen, DARK_GRAY, (250, 65), (250, CANVAS_HEIGHT - 10), 3)
        pygame.draw.arc(screen, DARK_GRAY, (130, CANVAS_HEIGHT - 25, 120, 30), 3.14, 0, 3)

        for i in range(PARTITION_COUNT):
            x_pos = 400 + (i * 65)
            pygame.draw.rect(screen, GRAY, (x_pos, 200, 55, CANVAS_HEIGHT - 200), 1)
            label = font.render(f"P{i}", True, BLACK)
            screen.blit(label, (x_pos + 15, CANVAS_HEIGHT + 5))
            h_val = partition_total_heights[i]
            h_text = font.render(f"{h_val}", True, BLUE)
            screen.blit(h_text, (x_pos + 10, CANVAS_HEIGHT - h_val - 25 if h_val < 450 else 200))

        # Greedy 로직 (LPT: 큰 것부터 하나씩 꺼내기)
        if started and not active_unit and units:
            active_unit = units.pop() # 리스트의 맨 뒤(원기둥의 맨 위)에서 추출
            target_idx = partition_total_heights.index(min(partition_total_heights))
            
            target_x = 400 + (target_idx * 65) + 5
            target_y = (CANVAS_HEIGHT - 10) - partition_total_heights[target_idx] - active_unit.height
            
            active_unit.target_pos = (target_x, target_y)
            active_unit.is_moving = True
            active_unit.rect.width = 45

        # 유닛 렌더링
        for u in units:
            pygame.draw.rect(screen, ORANGE, u.rect)
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

        msg = "S: 시작 | R: 큰 데이터부터 쌓기(LPT) | ESC: 초기화 | 정렬: " + ("ON" if sorted_mode else "OFF")
        guide = font.render(msg, True, DARK_GRAY)
        screen.blit(guide, (20, 50))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    run_simulation()
