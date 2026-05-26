import pygame
import time
import random
import sys
import math
import os
import json

# --- THÔNG TIN PHIÊN BẢN ---
VERSION = "1.0.0"
UPDATE_URL = "https://raw.githubusercontent.com/dovanphit1-creator/RanDoiKhang/refs/heads/main/version.json"
# --- CẤU HÌNH HẰNG SỐ ---
WIDTH, HEIGHT = 600, 400
SNAKE_BLOCK = 10
BASE_SPEED = 7
BOOST_SPEED_MULTIPLIER = 3.0
TIME_LIMIT = 150  # 2m 30s
SCORE_LIMIT = 50

# --- MÀU SẮC ---
WHITE = (255, 255, 255)
BLACK = (220, 220, 240)  # Chuyển BLACK thành màu chữ sáng (Off-white)
RED_LED = (255, 50, 50)
GREEN_LED = (50, 255, 50)
BLUE_LED = (50, 150, 255)
MAGENTA_LED = (255, 50, 255)
YELLOW_LED = (255, 255, 50)
ORANGE_LED = (255, 165, 0)
SNAKE_COLORS = [BLUE_LED, (0, 255, 255), (200, 50, 255), (255, 150, 50), (255, 50, 150)]
PAPER_BASE = (10, 12, 18)    # Nền tối sâu (Deep Dark Blue)
PAPER_GRAIN = (20, 24, 35)   # Hạt nhiễu tối
GRID_LINE = (35, 40, 60)     # Đường lưới xanh thẫm

# --- CẤU HÌNH ĐIỀU KHIỂN CẢM ỨNG ---
TOUCH_UI_ALPHA = 100
BTN_COLOR = (200, 200, 200, TOUCH_UI_ALPHA)
BTN_SIZE = 50
PAD_MARGIN = 20

# --- CẤU HÌNH MỒI ĐẶC BIỆT ---
SF1_RARITY = 150 # Xuất hiện thường xuyên hơn
SF1_REWARD = 50
SF1_LENGTH = 5
SF2_RARITY = 400 # Tỉ lệ xuất hiện vừa phải
SF2_REWARD = 150
SF2_LENGTH = 15
SF3_RARITY = 800 # Hiếm nhưng chắc chắn sẽ gặp trong trận
SF3_REWARD = 300
SF3_LENGTH = 30

# --- KHỞI TẠO HỆ THỐNG ---
try:
    # Khởi tạo mixer với cấu hình tiêu chuẩn nhất
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    if not pygame.mixer.get_init():
        pygame.mixer.init()
except Exception as e:
    print(f"Hệ thống âm thanh không khởi tạo được: {e}")

def get_path(filename, is_data=False):
    """
    Xử lý đường dẫn linh hoạt để không bị mất file khi đóng gói hoặc di chuyển:
    - is_data=False: Cho file âm thanh (Resources). Khi đóng gói EXE, nó nằm trong thư mục tạm.
    - is_data=True: Cho file .json (Dữ liệu). Nó phải nằm cạnh file EXE để không bị xóa.
    """
    if hasattr(sys, '_MEIPASS'):
        if is_data:
            # File JSON sẽ được lưu ngay cạnh file .exe của bạn
            return os.path.join(os.path.dirname(sys.executable), filename)
        else:
            # File âm thanh được lấy từ thư mục tạm khi đóng gói --add-data
            return os.path.join(sys._MEIPASS, filename)
    # Trường hợp chạy file .py bình thường
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def load_sfx(file_name):
    """Tải âm thanh và thông báo lỗi cụ thể ra console nếu thất bại"""
    path = get_path(file_name, is_data=False)
    if not os.path.exists(path):
        print(f"CẢNH BÁO: Thiếu file âm thanh: {path}")
        return None
    try:
        sound = pygame.mixer.Sound(path)
        sound.set_volume(1.0)
        return sound
    except Exception as e:
        print(f"LỖI: File {file_name} không hợp lệ hoặc hỏng: {e}")
        return None

# Tải âm thanh (Hãy đảm bảo file .wav tồn tại trong cùng thư mục với game.py)
sfx_eat = load_sfx("eat.wav")
sfx_hit = load_sfx("hit.wav")
sfx_win = load_sfx("win.wav")
sfx_lose = load_sfx("lose.wav") or sfx_hit  # Dùng âm thanh va chạm nếu thiếu file thua
sfx_click = load_sfx("click.wav")

# Sử dụng RESIZABLE để cửa sổ và không gian game đồng bộ hoàn toàn
dis = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption('Rắn Săn Mồi - Phiên bản E-Ink Pro')
clock = pygame.time.Clock()

# --- CÁC HÀM TRỢ NĂNG ---
def create_paper_texture():
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill(PAPER_BASE)
    for _ in range(5000):
        rx, ry = random.randint(0, WIDTH-1), random.randint(0, HEIGHT-1)
        pygame.draw.rect(surf, PAPER_GRAIN, [rx, ry, 1, 1])
    for y in range(0, HEIGHT, 3):
        line = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
        line.fill((255, 255, 255, 8)) # Scanlines sáng nhẹ trên nền tối
        surf.blit(line, (0, y))
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (0, 0, 0, 40), [0, 0, WIDTH, HEIGHT], border_radius=50) # Vignette mạnh hơn
    surf.blit(overlay, (0, 0))
    return surf

# --- HỆ THỐNG AI PHÁT TRIỂN (Q-LEARNING) ---
class SnakeAI:
    def __init__(self, filename="snake_ai.json"):
        self.filename = get_path(filename, is_data=True)
        self.q_table = {}
        self.lr = 0.95  # Tốc độ học tối đa (gần như ghi nhớ tức thì)
        self.discount = 0.9
        self.epsilon_min = 0.05  # Tỷ lệ ngẫu nhiên tối thiểu khi đã trưởng thành
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.q_table = json.load(f)
            except: self.q_table = {}

    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.q_table, f)

    def get_state(self, head, food, body, other_body, width, height, is_target_special, p_vel, vel):
        # State rút gọn: Nguy hiểm xung quanh + Hướng mồi
        x, y = head
        fx, fy = food
        
        # Nguy hiểm (Thân mình, thân người chơi, tường)
        def is_unsafe(pt):
            px, py = pt
            # AI nhận biết tường là vùng chết
            return px < 0 or px >= width or py < 0 or py >= height or list(pt) in other_body

        state = (
            is_unsafe((x, y - SNAKE_BLOCK)), # Danger Up
            is_unsafe((x, y + SNAKE_BLOCK)), # Danger Down
            is_unsafe((x - SNAKE_BLOCK, y)), # Danger Left
            is_unsafe((x + SNAKE_BLOCK, y)), # Danger Right
            fx < x,  # Food Left
            fx > x,  # Food Right
            fy < y,  # Food Up
            fy > y,  # Food Down
            is_target_special,
            p_vel, # Nhận diện hướng di chuyển của người chơi để né tránh
            vel # Hướng di chuyển hiện tại (dx, dy) để tránh quay đầu lỗi
        )
        return str(state)

    def choose_action(self, state):
        # Hệ thống tiến hóa: Epsilon giảm dần dựa trên số lượng trạng thái đã học
        # Bắt đầu từ 1.0 (100% ngẫu nhiên) và giảm dần về epsilon_min (5%)
        # Giảm ngưỡng xuống 300 để AI đạt trạng thái "thiên tài" cực kỳ nhanh
        dynamic_epsilon = max(self.epsilon_min, 1.0 - (len(self.q_table) / 300))
        
        if random.random() < dynamic_epsilon or state not in self.q_table:
            # Ưu tiên các hành động di chuyển cơ bản trong giai đoạn đầu
            if random.random() < 0.8: return random.randint(0, 3)
            return random.randint(0, 7)
        
        # Chọn ngẫu nhiên giữa các hành động có giá trị cao nhất bằng nhau để tránh kẹt logic
        max_val = max(self.q_table[state])
        actions = [i for i, v in enumerate(self.q_table[state]) if v == max_val]
        return random.choice(actions)

    def learn(self, state, action, reward, next_state):
        if state not in self.q_table: self.q_table[state] = [0.0] * 8
        if next_state not in self.q_table: self.q_table[next_state] = [0.0] * 8
        
        old_value = self.q_table[state][action]
        next_max = max(self.q_table[next_state])
        self.q_table[state][action] = old_value + self.lr * (reward + self.discount * next_max - old_value)

    def clear_data(self):
        self.q_table = {}
        self.save_data()

ai_agent = SnakeAI()

# --- HỆ THỐNG BỘ NÃO MỒI ĐẶC BIỆT ---
class FoodAI:
    def __init__(self, filename="food_ai.json"):
        self.filename = get_path(filename, is_data=True)
        self.q_table = {"sf1": {}, "sf2": {}, "sf3": {}}
        self.lr = 0.95 # Mồi cũng học với tốc độ bàn thờ
        self.discount = 0.9 # Nhìn xa trông rộng hơn để né tránh
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.q_table = json.load(f)
            except: self.q_table = {"sf1": {}, "sf2": {}, "sf3": {}}

    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.q_table, f)

    def get_state(self, food_pos, p_pos, ai_pos, width, height):
        fx, fy = food_pos
        px, py = p_pos
        ax, ay = ai_pos
        # Hướng tương đối của 2 con rắn đối với mồi
        rel_p = (1 if px > fx else -1 if px < fx else 0, 1 if py > fy else -1 if py < fy else 0)
        rel_a = (1 if ax > fx else -1 if ax < fx else 0, 1 if ay > fy else -1 if ay < fy else 0)
        # Nhận biết tường xung quanh
        near_wall = (fy < SNAKE_BLOCK, fy >= height - SNAKE_BLOCK, fx < SNAKE_BLOCK, fx >= width - SNAKE_BLOCK)
        return str((rel_p, rel_a, near_wall))

    def choose_action(self, f_type, state):
        # 0-3: Up, Down, Left, Right, 4: Stay
        # Differentiate exploration: SF1 is clumsy, SF3 is precise
        exploration = 0.2 if f_type == "sf1" else 0.05 if f_type == "sf2" else 0.01
        if state not in self.q_table[f_type] or random.random() < exploration:
            return random.randint(0, 4)
        max_val = max(self.q_table[f_type][state])
        # Chọn ngẫu nhiên giữa các hành động tốt nhất để tránh kẹt
        best_actions = [i for i, v in enumerate(self.q_table[f_type][state]) if v == max_val]
        return random.choice(best_actions)

    def learn(self, f_type, state, action, reward, next_state):
        if state not in self.q_table[f_type]: self.q_table[f_type][state] = [0.0] * 5
        if next_state not in self.q_table[f_type]: self.q_table[f_type][next_state] = [0.0] * 5
        
        old_val = self.q_table[f_type][state][action]
        next_max = max(self.q_table[f_type][next_state])
        self.q_table[f_type][state][action] = old_val + self.lr * (reward + self.discount * next_max - old_val)

    def clear_data(self):
        self.q_table = {"sf1": {}, "sf2": {}, "sf3": {}}
        self.save_data()

food_agent = FoodAI()

# --- HỆ THỐNG THỐNG KÊ ---
class GameStats:
    def __init__(self, filename="game_stats.json"):
        self.filename = get_path(filename, is_data=True)
        self.stats = {"wins": 0, "losses": 0, "draws": 0, "total": 0}
        self.load_stats()

    def load_stats(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.stats = json.load(f)
            except: self.stats = {"wins": 0, "losses": 0, "draws": 0, "total": 0}

    def save_stats(self):
        with open(self.filename, 'w') as f:
            json.dump(self.stats, f)

    def record_win(self): self.stats["wins"] += 1; self.stats["total"] += 1; self.save_stats()
    def record_loss(self): self.stats["losses"] += 1; self.stats["total"] += 1; self.save_stats()
    def record_draw(self): self.stats["draws"] += 1; self.stats["total"] += 1; self.save_stats()

    def clear_stats(self):
        self.stats = {"wins": 0, "losses": 0, "draws": 0, "total": 0}
        self.save_stats()

game_stats = GameStats()

PAPER_TEXTURE = create_paper_texture()
font_style = pygame.font.SysFont("Consolas", 22, bold=True)
score_font = pygame.font.SysFont("Consolas", 20)
result_font = pygame.font.SysFont("Consolas", 32, bold=True)

def get_touch_rects():
    """Lấy vùng va chạm của các nút điều khiển"""
    # D-pad bên trái
    up_rect = pygame.Rect(PAD_MARGIN + BTN_SIZE, HEIGHT - PAD_MARGIN - BTN_SIZE * 3, BTN_SIZE, BTN_SIZE)
    down_rect = pygame.Rect(PAD_MARGIN + BTN_SIZE, HEIGHT - PAD_MARGIN - BTN_SIZE, BTN_SIZE, BTN_SIZE)
    left_rect = pygame.Rect(PAD_MARGIN, HEIGHT - PAD_MARGIN - BTN_SIZE * 2, BTN_SIZE, BTN_SIZE)
    right_rect = pygame.Rect(PAD_MARGIN + BTN_SIZE * 2, HEIGHT - PAD_MARGIN - BTN_SIZE * 2, BTN_SIZE, BTN_SIZE)
    # Nút Boost bên phải
    boost_rect = pygame.Rect(WIDTH - PAD_MARGIN - BTN_SIZE * 1.5, HEIGHT - PAD_MARGIN - BTN_SIZE * 1.5, BTN_SIZE * 1.5, BTN_SIZE * 1.5)
    return up_rect, down_rect, left_rect, right_rect, boost_rect

def draw_touch_controls(surface):
    """Vẽ các nút điều khiển ảo lên màn hình"""
    rects = get_touch_rects()
    labels = ["▲", "▼", "◄", "►", "⚡"]
    for rect, label in zip(rects, labels):
        s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(s, BTN_COLOR, s.get_rect(), border_radius=10)
        draw_text_prominent(s, label, score_font, WHITE, (rect.width//2, rect.height//2))
        surface.blit(s, (rect.x, rect.y))

def draw_aura(surface, color, pos_rect, spread=15):
    aura_surf = pygame.Surface((pos_rect.width + spread*2, pos_rect.height + spread*2), pygame.SRCALPHA)
    for i in range(spread, 0, -1):
        alpha = int(80 * (1 - i/spread)) # Độ mờ giảm dần
        s_color = (*color, alpha)
        inflated_rect = pygame.Rect(spread-i, spread-i, pos_rect.width + i*2, pos_rect.height + i*2)
        pygame.draw.rect(aura_surf, s_color, inflated_rect, border_radius=i)
    surface.blit(aura_surf, (pos_rect.x - spread, pos_rect.y - spread))

def draw_text_prominent(surface, text, font, color, center_pos, glow_color=None):
    if glow_color:
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)]:
            glow_surf = font.render(text, True, glow_color)
            glow_rect = glow_surf.get_rect(center=(center_pos[0] + ox, center_pos[1] + oy))
            surface.blit(glow_surf, glow_rect)
    else:
        shadow_surf = font.render(text, True, (0, 0, 0)) # Bóng đổ đen tuyệt đối
        shadow_rect = shadow_surf.get_rect(center=(center_pos[0] + 2, center_pos[1] + 2))
        surface.blit(shadow_surf, shadow_rect)
    main_surf = font.render(text, True, color)
    main_rect = main_surf.get_rect(center=center_pos)
    surface.blit(main_surf, main_rect)

def draw_stats(score, ai_score, time_left, is_boosting=False):
    # Hiển thị điểm của người chơi
    draw_text_prominent(dis, f"NGƯỜI CHƠI: {score}/{SCORE_LIMIT}", score_font, BLACK, (120, 25))
    # Hiển thị bảng điểm của đối thủ AI (màu Magenta đặc trưng)
    draw_text_prominent(dis, f"ĐIỂM AI: {ai_score}/{SCORE_LIMIT}", score_font, MAGENTA_LED, (120, 50))
    current_spd = BASE_SPEED * BOOST_SPEED_MULTIPLIER if is_boosting else BASE_SPEED
    draw_text_prominent(dis, f"TỐC ĐỘ: {int(current_spd)}", score_font, BLACK, (WIDTH // 2, 25))
    minutes = int(time_left // 60)
    seconds = int(time_left % 60)
    draw_text_prominent(dis, f"THỜI GIAN: {minutes:02d}:{seconds:02d}", score_font, BLACK, (WIDTH - 150, 25))

def draw_grid():
    """Vẽ lưới với hiệu ứng đèn LED cầu vồng rực rỡ (Rainbow LED) chuyển động liên tục"""
    t = pygame.time.get_ticks() * 0.003
    for x in range(0, WIDTH, SNAKE_BLOCK):
        phase = t + x * 0.01
        # Tạo màu cầu vồng rực rỡ bằng cách lệch pha 3 kênh RGB (120 độ mỗi kênh)
        r = int(127 + 127 * math.sin(phase))
        g = int(127 + 127 * math.sin(phase + 2 * math.pi / 3))
        b = int(127 + 127 * math.sin(phase + 4 * math.pi / 3))
        # Giữ độ rực rỡ ở mức 40% để đẹp mắt mà không gây lóa mắt trên nền tối
        pygame.draw.line(dis, (int(r * 0.4), int(g * 0.4), int(b * 0.4)), (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, SNAKE_BLOCK):
        phase = t + y * 0.01 + math.pi
        r = int(127 + 127 * math.sin(phase))
        g = int(127 + 127 * math.sin(phase + 2 * math.pi / 3))
        b = int(127 + 127 * math.sin(phase + 4 * math.pi / 3))
        pygame.draw.line(dis, (int(r * 0.4), int(g * 0.4), int(b * 0.4)), (0, y), (WIDTH, y))

def our_snake(snake_block, snake_list, is_stunned=False, snake_color=BLUE_LED, flash_color=None, bg_flash=0, is_boosting=False):
    radius = SNAKE_BLOCK // 2
    
    # Màu sắc cơ bản cho thân và đầu
    body_color = [snake_color[0] // 2, snake_color[1] // 2, snake_color[2] // 2]
    head_draw_color = list(YELLOW_LED if is_stunned else snake_color)

    # Pha trộn màu nếu đang có hiệu ứng flash (va chạm/ăn mồi)
    if bg_flash > 0 and flash_color:
        head_draw_color = [int(head_draw_color[i] * (1 - bg_flash) + flash_color[i] * bg_flash) for i in range(3)]
        body_color = [int(body_color[i] * (1 - bg_flash) + (flash_color[i] // 2) * bg_flash) for i in range(3)]

    # Surface hào quang cho thân để dùng chung (tránh tạo liên tục trong loop để tối ưu hiệu năng)
    glow_surf = None
    glow_spread = 0
    if is_boosting or bg_flash > 0.1:
        glow_spread = 10 if is_boosting else 6
        glow_alpha = int(180 * max(bg_flash, 0.5 if is_boosting else 0))
        glow_surf = pygame.Surface((radius*2 + glow_spread*2, radius*2 + glow_spread*2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*body_color, glow_alpha), (radius + glow_spread, radius + glow_spread), radius + glow_spread)

    for i, x in enumerate(snake_list):
        center_x = int(x[0] + radius)
        center_y = int(x[1] + radius)
        if i == len(snake_list) - 1:
            head_rect = pygame.Rect(x[0], x[1], SNAKE_BLOCK, SNAKE_BLOCK)
            spread = 18 if is_stunned else 12
            if is_boosting: spread += 10 # Hào quang đầu rực rỡ hơn khi boost
            draw_aura(dis, head_draw_color, head_rect, spread=spread)
            pygame.draw.circle(dis, BLACK, (center_x, center_y), radius)
        else:
            if glow_surf:
                dis.blit(glow_surf, (center_x - (radius + glow_spread), center_y - (radius + glow_spread)))
            pygame.draw.circle(dis, body_color, (center_x, center_y), radius)

def main_menu(initial_color_idx=0):
    global WIDTH, HEIGHT, PAPER_TEXTURE, dis
    selected_color_idx = initial_color_idx

    def update_menu_dims(w, h):
        global WIDTH, HEIGHT, PAPER_TEXTURE, dis
        WIDTH, HEIGHT = w, h
        dis = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        PAPER_TEXTURE = create_paper_texture()

    while True:
        # Tạo hiệu ứng nhịp đập cho hào quang nút bấm
        pulse = abs(math.sin(pygame.time.get_ticks() * 0.005)) * 5

        # Cập nhật vị trí nút bấm theo kích thước cửa sổ hiện tại
        start_btn = pygame.Rect(WIDTH // 2 - 90, HEIGHT // 2 + 10, 180, 40)
        quit_btn = pygame.Rect(WIDTH // 2 - 90, HEIGHT // 2 + 60, 180, 40)
        reset_ai_btn = pygame.Rect(WIDTH // 2 - 90, HEIGHT - 50, 180, 35)
        color_btns = [pygame.Rect(WIDTH // 2 - 80 + i * 35, HEIGHT // 2 + 140, 20, 20) for i in range(len(SNAKE_COLORS))]
        
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.VIDEORESIZE:
                update_menu_dims(event.w, event.h)
                
            if event.type == pygame.KEYDOWN:
                # Hỗ trợ phím Q hoặc nút Back trên Android
                if event.key == pygame.K_q or event.key == getattr(pygame, 'K_AC_BACK', -1):
                    if sfx_click: sfx_click.play()
                    return False
                if event.key == pygame.K_s:
                    if sfx_click: sfx_click.play()
                    return selected_color_idx
            if event.type == pygame.MOUSEBUTTONDOWN:
                if start_btn.collidepoint(event.pos):
                    if sfx_click: sfx_click.play()
                    return selected_color_idx
                if quit_btn.collidepoint(event.pos):
                    if sfx_click: sfx_click.play()
                    pygame.time.delay(100)
                    return False
                if reset_ai_btn.collidepoint(event.pos):
                    if sfx_click: sfx_click.play()
                    ai_agent.clear_data()
                    food_agent.clear_data()
                    game_stats.clear_stats()
                for i, btn in enumerate(color_btns):
                    if btn.collidepoint(event.pos):
                        selected_color_idx = i
                        if sfx_click: sfx_click.play()

        dis.blit(PAPER_TEXTURE, (0, 0))
        draw_grid() # Hiệu ứng LED đa sắc độc lập cho Menu

        # Hiển thị phiên bản và thông báo cập nhật
        draw_text_prominent(dis, f"Phiên bản: {VERSION}", score_font, BLACK, (WIDTH // 2, HEIGHT - 20))

        # Bảng thống kê trận đấu
        stats_box = pygame.Rect(20, 20, 160, 110)
        pygame.draw.rect(dis, BLACK, stats_box, 2)
        draw_text_prominent(dis, f"TỔNG SỐ: {game_stats.stats['total']}", score_font, BLACK, (stats_box.centerx, stats_box.top + 20))
        draw_text_prominent(dis, f"THẮNG  : {game_stats.stats['wins']}", score_font, GREEN_LED, (stats_box.centerx, stats_box.top + 45))
        draw_text_prominent(dis, f"THUA   : {game_stats.stats['losses']}", score_font, RED_LED, (stats_box.centerx, stats_box.top + 70))
        draw_text_prominent(dis, f"HÒA    : {game_stats.stats['draws']}", score_font, YELLOW_LED, (stats_box.centerx, stats_box.top + 95))

        # Bảng dữ liệu AI đã học được
        ai_data_box = pygame.Rect(WIDTH - 185, 20, 165, 65)
        pygame.draw.rect(dis, BLACK, ai_data_box, 2)
        draw_text_prominent(dis, "KINH NGHIỆM AI", score_font, MAGENTA_LED, (ai_data_box.centerx, ai_data_box.top + 20))
        learned_states = len(ai_agent.q_table)
        draw_text_prominent(dis, f"{learned_states} trạng thái", score_font, BLACK, (ai_data_box.centerx, ai_data_box.top + 45))

        # Bảng dữ liệu Mồi đã học được
        food_data_box = pygame.Rect(WIDTH - 185, 100, 165, 105)
        pygame.draw.rect(dis, BLACK, food_data_box, 2)
        draw_text_prominent(dis, "KINH NGHIỆM MỒI", score_font, GREEN_LED, (food_data_box.centerx, food_data_box.top + 20))
        draw_text_prominent(dis, f"Mồi Vàng: {len(food_agent.q_table['sf1'])}", score_font, BLACK, (food_data_box.centerx, food_data_box.top + 45))
        draw_text_prominent(dis, f"Mồi Cam: {len(food_agent.q_table['sf2'])}", score_font, BLACK, (food_data_box.centerx, food_data_box.top + 70))
        draw_text_prominent(dis, f"Mồi Trắng: {len(food_agent.q_table['sf3'])}", score_font, BLACK, (food_data_box.centerx, food_data_box.top + 95))

        pygame.draw.rect(dis, BLACK, [15, 15, WIDTH - 30, HEIGHT - 30], 2)
        draw_text_prominent(dis, "RẮN SĂN MỒI", result_font, BLACK, (WIDTH // 2, HEIGHT // 2 - 50), BLUE_LED)
        start_color = BLUE_LED if start_btn.collidepoint(mouse_pos) else BLACK
        draw_aura(dis, BLUE_LED, start_btn, spread=8 + int(pulse))
        pygame.draw.rect(dis, start_color, start_btn, 2)
        quit_color = RED_LED if quit_btn.collidepoint(mouse_pos) else BLACK
        pygame.draw.rect(dis, quit_color, quit_btn, 2)
        start_txt = font_style.render("BẮT ĐẦU (S)", True, start_color)
        quit_txt = font_style.render("THOÁT (Q)", True, quit_color)
        dis.blit(start_txt, start_txt.get_rect(center=start_btn.center))
        dis.blit(quit_txt, quit_txt.get_rect(center=quit_btn.center))

        reset_ai_color = YELLOW_LED if reset_ai_btn.collidepoint(mouse_pos) else BLACK
        pygame.draw.rect(dis, reset_ai_color, reset_ai_btn, 2)
        reset_ai_txt = score_font.render("KHÔI PHỤC", True, reset_ai_color)
        dis.blit(reset_ai_txt, reset_ai_txt.get_rect(center=reset_ai_btn.center))

        draw_text_prominent(dis, "CHỌN MÀU RẮN:", score_font, BLACK, (WIDTH // 2, HEIGHT // 2 + 115))
        for i, color in enumerate(SNAKE_COLORS):
            if i == selected_color_idx:
                draw_aura(dis, color, color_btns[i], spread=10)
                pygame.draw.circle(dis, WHITE, color_btns[i].center, 12, 1)
            pygame.draw.circle(dis, color, color_btns[i].center, 10)

        for i in range(5):
            pygame.draw.circle(dis, SNAKE_COLORS[selected_color_idx], (int(WIDTH / 2 - 40 + i * 20), int(HEIGHT / 2 + 175)), 8)
        pygame.display.update()

def gameLoop(start_color_idx):
    global WIDTH, HEIGHT, PAPER_TEXTURE, dis
    game_close = False
    start_ticks = pygame.time.get_ticks()
    paused = False
    stun_until = 0
    snake_color_idx = start_color_idx
    end_reason = "KẾT THÚC!"
    is_boosting = False
    bg_flash = 0.0  # Độ cường độ của hiệu ứng flash nền (0.0 đến 1.0)
    flash_color = GREEN_LED
    reason_color = RED_LED

    # Người chơi bắt đầu ở trung tâm
    x1 = (WIDTH // 2 // SNAKE_BLOCK) * SNAKE_BLOCK 
    y1 = (HEIGHT // 2 // SNAKE_BLOCK) * SNAKE_BLOCK
    x1_change, y1_change = 0, 0
    snake_List = [[x1, y1]]
    Length_of_snake = 1

    # Khởi tạo đối thủ AI
    ai_x_change, ai_y_change = 0, 0
    ai_x, ai_y = SNAKE_BLOCK * 2, SNAKE_BLOCK * 2 # AI bắt đầu ở góc trên bên trái
    ai_snake_list = []
    ai_length = 1
    ai_stun_until = 0
    ai_last_state = None
    ai_last_action = None
    ai_last_target = None # Lưu mục tiêu cũ để học tập chính xác
    ai_prev_dist = 0
    ai_last_reward = 0  # Tích lũy phần thưởng từ frame trước
    
    # Khởi tạo hành động của mồi để học tập
    sf1_last_action = 4
    sf2_last_action = 4
    sf3_last_action = 4
    # Khởi tạo AI có vận tốc ban đầu để tránh đứng im
    ai_x_change, ai_y_change = SNAKE_BLOCK, 0 
    ai_is_boosting = False
    ai_bg_flash = 0.0
    ai_flash_color = GREEN_LED

    # Khởi tạo các loại mồi đặc biệt
    sf1_active = False
    sf1_x, sf1_y = -100, -100
    sf2_active = False
    sf2_x, sf2_y = -100, -100
    sf3_active = False
    sf3_x, sf3_y = -100, -100

    def get_safe_food_pos(all_occupied_positions):
        """Tìm vị trí đặt mồi không đè lên thân rắn và nằm trong màn hình"""
        while True:
            cols = WIDTH // SNAKE_BLOCK
            rows = HEIGHT // SNAKE_BLOCK
            fx = random.randint(0, max(0, cols - 1)) * SNAKE_BLOCK
            fy = random.randint(0, max(0, rows - 1)) * SNAKE_BLOCK
            if [fx, fy] not in all_occupied_positions:
                return int(fx), int(fy)

    def sync_entities_to_window():
        """Đảm bảo mọi thực thể nằm trong giới hạn màn hình sau khi resize và bám lưới"""
        nonlocal foodx, foody, sf1_x, sf1_y, sf2_x, sf2_y, sf3_x, sf3_y, x1, y1, ai_x, ai_y
        max_x = (WIDTH // SNAKE_BLOCK - 1) * SNAKE_BLOCK
        max_y = (HEIGHT // SNAKE_BLOCK - 1) * SNAKE_BLOCK
        
        # Căn chỉnh lại tọa độ theo lưới SNAKE_BLOCK và giới hạn trong màn hình
        x1 = min(max(0, (x1 // SNAKE_BLOCK) * SNAKE_BLOCK), max_x)
        y1 = min(max(0, (y1 // SNAKE_BLOCK) * SNAKE_BLOCK), max_y)
        foodx = min(max(0, (foodx // SNAKE_BLOCK) * SNAKE_BLOCK), max_x)
        foody = min(max(0, (foody // SNAKE_BLOCK) * SNAKE_BLOCK), max_y)
        ai_x = min(max(0, (ai_x // SNAKE_BLOCK) * SNAKE_BLOCK), max_x)
        ai_y = min(max(0, (ai_y // SNAKE_BLOCK) * SNAKE_BLOCK), max_y)

        if sf1_active:
            sf1_x = min(max(0, (sf1_x // SNAKE_BLOCK) * SNAKE_BLOCK), max_x)
            sf1_y = min(max(0, (sf1_y // SNAKE_BLOCK) * SNAKE_BLOCK), max_y)
        if sf2_active:
            sf2_x = min(max(0, (sf2_x // SNAKE_BLOCK) * SNAKE_BLOCK), max_x)
            sf2_y = min(max(0, (sf2_y // SNAKE_BLOCK) * SNAKE_BLOCK), max_y)
        if sf3_active:
            sf3_x = min(max(0, (sf3_x // SNAKE_BLOCK) * SNAKE_BLOCK), max_x)
            sf3_y = min(max(0, (sf3_y // SNAKE_BLOCK) * SNAKE_BLOCK), max_y)

    def get_all_occupied_positions():
        positions = []
        for segment in snake_List: positions.append(segment)
        for segment in ai_snake_list: positions.append(segment)
        if sf1_active: positions.append([sf1_x, sf1_y])
        if sf2_active: positions.append([sf2_x, sf2_y])
        if sf3_active: positions.append([sf3_x, sf3_y])
        return positions

    # Khởi tạo AI ở vị trí an toàn, tránh trùng lặp ngay lúc đầu
    ai_x, ai_y = get_safe_food_pos(get_all_occupied_positions())
    ai_snake_list = [[ai_x, ai_y]]
    ai_last_target = (0, 0)
    ai_prev_dist = 0
    ai_last_reward = 0

    # Initialize food AI previous distances (for learning)
    sf1_prev_dist_p = abs(sf1_x - x1) + abs(sf1_y - y1)
    sf1_prev_dist_ai = abs(sf1_x - ai_x) + abs(sf1_y - ai_y)
    sf2_prev_dist_p = abs(sf2_x - x1) + abs(sf2_y - y1)
    sf2_prev_dist_ai = abs(sf2_x - ai_x) + abs(sf2_y - ai_y)
    sf3_prev_dist_p = abs(sf3_x - x1) + abs(sf3_y - y1)
    sf3_prev_dist_ai = abs(sf3_x - ai_x) + abs(sf3_y - ai_y)

    foodx, foody = get_safe_food_pos(get_all_occupied_positions())

    ai_last_target = (foodx, foody)
    ai_prev_dist = abs(ai_x - foodx) + abs(ai_y - foody)

    while True:
        # Nút bấm HUD luôn cập nhật theo kích thước thực tế
        pause_btn = pygame.Rect(WIDTH - 85, 7, 35, 35)
        home_btn = pygame.Rect(WIDTH - 42, 7, 35, 35)

        seconds_passed = (pygame.time.get_ticks() - start_ticks) / 1000
        time_left = max(0, TIME_LIMIT - seconds_passed)
        is_stunned = pygame.time.get_ticks() < stun_until

        # Tính toán AI Stun ở đây để dùng cho việc vẽ nếu cần
        ai_is_stunned = pygame.time.get_ticks() < ai_stun_until

        if paused:
            p_start = pygame.time.get_ticks()
            is_boosting = False
            ai_is_boosting = False
            if sfx_click: sfx_click.play()
            while paused:
                res_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 10, 200, 40)
                dis.blit(PAPER_TEXTURE, (0, 0))
                
                for p_event in pygame.event.get():
                    if p_event.type == pygame.QUIT:
                        pygame.quit(); sys.exit()
                    if p_event.type == pygame.KEYDOWN:
                        if p_event.key in [pygame.K_p, pygame.K_ESCAPE] or p_event.key == getattr(pygame, 'K_AC_BACK', -1):
                            paused = False
                    if p_event.type == pygame.MOUSEBUTTONDOWN:
                        # Bất kỳ cú chạm nào ngoài nút menu cũng có thể dùng để resume
                        paused = False

                draw_grid()
                
                # Vẽ các thực thể phía dưới lớp phủ tạm dừng để người chơi vẫn quan sát được
                our_snake(SNAKE_BLOCK, snake_List, is_stunned, SNAKE_COLORS[snake_color_idx], flash_color, bg_flash, False)
                our_snake(SNAKE_BLOCK, ai_snake_list, ai_is_stunned, MAGENTA_LED, ai_flash_color, ai_bg_flash, False)
                
                draw_text_prominent(dis, "TẠM DỪNG", result_font, WHITE, (WIDTH // 2, HEIGHT // 2 - 50), BLUE_LED)
                pygame.draw.rect(dis, BLACK, res_rect, 2)
                res_txt = font_style.render("TIẾP TỤC (P)", True, BLACK)
                dis.blit(res_txt, res_txt.get_rect(center=res_rect.center))
                
                draw_stats(Length_of_snake - 1, ai_length - 1, time_left, False)
                pygame.display.update()

            start_ticks += (pygame.time.get_ticks() - p_start) # Bù trừ thời gian đã tạm dừng
            if sfx_click: sfx_click.play()
            paused = False

        while game_close == True:
            mouse_pos = pygame.mouse.get_pos()
            retry_btn = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2, 200, 40)
            menu_btn = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 50, 200, 40)
            
            dis.blit(PAPER_TEXTURE, (0, 0))
            draw_grid()
            # Giữ hiển thị rắn trên màn hình kết thúc
            our_snake(SNAKE_BLOCK, snake_List, is_stunned, SNAKE_COLORS[snake_color_idx], flash_color, bg_flash, False)
            our_snake(SNAKE_BLOCK, ai_snake_list, ai_is_stunned, MAGENTA_LED, ai_flash_color, ai_bg_flash, False)
            
            draw_text_prominent(dis, end_reason, result_font, BLACK, (WIDTH // 2, HEIGHT // 2 - 80), reason_color)
            draw_aura(dis, RED_LED, retry_btn, spread=10)
            retry_color = RED_LED if retry_btn.collidepoint(mouse_pos) else BLACK
            pygame.draw.rect(dis, retry_color, retry_btn, 2)
            menu_color = BLUE_LED if menu_btn.collidepoint(mouse_pos) else BLACK
            pygame.draw.rect(dis, menu_color, menu_btn, 2)
            retry_txt = font_style.render("CHƠI LẠI (C)", True, retry_color)
            menu_txt = font_style.render("TRANG CHỦ (Q)", True, menu_color)
            dis.blit(retry_txt, retry_txt.get_rect(center=retry_btn.center))
            dis.blit(menu_txt, menu_txt.get_rect(center=menu_btn.center))
            draw_stats(Length_of_snake - 1, ai_length - 1, time_left, is_boosting)
            pygame.display.update()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.VIDEORESIZE:
                    WIDTH, HEIGHT = event.w, event.h
                    dis = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                    PAPER_TEXTURE = create_paper_texture()
                    sync_entities_to_window()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        if sfx_click: sfx_click.play()
                        return False, snake_color_idx
                    if event.key == pygame.K_c:
                        if sfx_click: sfx_click.play()
                        return True, snake_color_idx
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if retry_btn.collidepoint(event.pos):
                        if sfx_click: sfx_click.play()
                        return True, snake_color_idx
                    if menu_btn.collidepoint(event.pos):
                        if sfx_click: sfx_click.play()
                        return False, snake_color_idx

        # --- LOGIC AI ĐỐI THỦ ---
        ai_age = len(ai_agent.q_table) # "Tuổi" của AI dựa trên số trạng thái đã học
        
        # Danh sách các mục tiêu tiềm năng mà AI có thể nhìn thấy và "đủ tuổi" để quan tâm
        potential_targets = []
        
        # Mồi thường (luôn có thể nhìn thấy)
        potential_targets.append({'type': 0, 'x': foodx, 'y': foody, 'reward': 10})

        # SF1 (Thiếu niên: >= 100 trạng thái)
        if sf1_active and ai_age >= 100:
            potential_targets.append({'type': 1, 'x': sf1_x, 'y': sf1_y, 'reward': SF1_REWARD})
        
        # SF2 (Trưởng thành: >= 500 trạng thái)
        if sf2_active and ai_age >= 500:
            potential_targets.append({'type': 2, 'x': sf2_x, 'y': sf2_y, 'reward': SF2_REWARD})

        # SF3 (Già dặn kinh nghiệm: >= 1000 trạng thái)
        if sf3_active and ai_age >= 1000:
            potential_targets.append({'type': 3, 'x': sf3_x, 'y': sf3_y, 'reward': SF3_REWARD})

        # AI ưu tiên mục tiêu có phần thưởng cao nhất mà nó "biết"
        potential_targets.sort(key=lambda t: t['reward'], reverse=True)

        # Chọn mục tiêu ưu tiên nhất
        chosen_target = potential_targets[0]
        target_food_x, target_food_y = chosen_target['x'], chosen_target['y']
        is_target_special = chosen_target['type'] > 0 # True nếu mục tiêu là mồi đặc biệt

        ai_state = ai_agent.get_state((ai_x, ai_y), (target_food_x, target_food_y), ai_snake_list, snake_List, WIDTH, HEIGHT, is_target_special, (x1_change, y1_change), (ai_x_change, ai_y_change))
        
        # AI Thiên tài học hỏi từ frame trước
        if ai_last_state and ai_last_action is not None:
            new_dist = abs(ai_x - ai_last_target[0]) + abs(ai_y - ai_last_target[1])
            dist_reward = 50 if new_dist < ai_prev_dist else -60 # Phạt/thưởng khoảng cách gắt hơn
            ai_agent.learn(ai_last_state, ai_last_action, ai_last_reward + dist_reward, ai_state)
            ai_last_reward = 0 # Reset sau khi học

        if not ai_is_stunned:
            ai_action = ai_agent.choose_action(ai_state)
            ai_last_state, ai_last_action = ai_state, ai_action
            ai_dir = ai_action % 4
            ai_is_boosting = (ai_action // 4) == 1
            
            if ai_dir == 0: ai_x_change, ai_y_change = 0, -SNAKE_BLOCK
            elif ai_dir == 1: ai_x_change, ai_y_change = 0, SNAKE_BLOCK
            elif ai_dir == 2: ai_x_change, ai_y_change = -SNAKE_BLOCK, 0
            elif ai_dir == 3: ai_x_change, ai_y_change = SNAKE_BLOCK, 0
        else:
            ai_is_boosting = False
            ai_last_action = None

        ai_prev_dist = abs(ai_x - target_food_x) + abs(ai_y - target_food_y)
        ai_last_target = (target_food_x, target_food_y)

        ai_new_x = ai_x + ai_x_change
        ai_new_y = ai_y + ai_y_change

        # Xử lý di chuyển và va chạm biên cho AI
        if (ai_new_x >= WIDTH or ai_new_x < 0 or ai_new_y >= HEIGHT or ai_new_y < 0) and not ai_is_stunned:
            if ai_length > 1:
                ai_length -= 1
                if ai_new_x >= WIDTH: ai_x -= SNAKE_BLOCK
                elif ai_new_x < 0: ai_x += SNAKE_BLOCK
                elif ai_new_y >= HEIGHT: ai_y -= SNAKE_BLOCK
                elif ai_new_y < 0: ai_y += SNAKE_BLOCK
                ai_x_change = ai_y_change = 0
                if ai_snake_list: ai_snake_list[-1] = [ai_x, ai_y]
                ai_stun_until = pygame.time.get_ticks() + 500 # Giảm stun để AI linh hoạt hơn
                ai_is_boosting = False
                ai_bg_flash = 0.4
                ai_flash_color = RED_LED
                if sfx_hit: sfx_hit.play()
                ai_agent.learn(ai_state, ai_action, -8, ai_state)
            else:
                if sfx_hit: sfx_hit.play()
                ai_agent.learn(ai_state, ai_action, -20, ai_state)
                p_score = Length_of_snake - 1
                a_score = ai_length - 1
                if p_score > a_score:
                    end_reason = "AI VA CHẠM! BẠN THẮNG!"
                    reason_color = GREEN_LED
                    if sfx_win: sfx_win.play()
                    game_stats.record_win()
                elif a_score > p_score:
                    end_reason = "AI VA CHẠM! AI VẪN THẮNG!"
                    reason_color = MAGENTA_LED
                    if sfx_lose: sfx_lose.play()
                    game_stats.record_loss()
                game_close = True
        else:
            ai_x += ai_x_change
            ai_y += ai_y_change
            
        ai_snake_list.append([ai_x, ai_y])
        while len(ai_snake_list) > ai_length:
            del ai_snake_list[0]

        # AI ăn mồi
        if ai_x == foodx and ai_y == foody:
            ai_length += 1
            foodx, foody = get_safe_food_pos(get_all_occupied_positions())
            if sfx_eat: sfx_eat.play()
            ai_bg_flash = 0.3
            ai_flash_color = GREEN_LED
            ai_last_reward += 1000 # Ăn mồi thường là một thành tựu lớn
        
        # AI ăn SF1
        if sf1_active and ai_x == sf1_x and ai_y == sf1_y:
            ai_length += SF1_LENGTH
            sf1_active = False
            # Phạt mồi dựa trên hành động cuối cùng
            f_death_state = food_agent.get_state((sf1_x, sf1_y), (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT)
            food_agent.learn("sf1", f_death_state, sf1_last_action, -100, f_death_state)
            if sfx_eat: sfx_eat.play()
            ai_bg_flash = 0.5
            ai_flash_color = YELLOW_LED
            ai_last_reward += 2000
        
        # AI ăn SF2
        if sf2_active and ai_x == sf2_x and ai_y == sf2_y:
            ai_length += SF2_LENGTH
            sf2_active = False
            f_death_state = food_agent.get_state((sf2_x, sf2_y), (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT)
            food_agent.learn("sf2", f_death_state, sf2_last_action, -100, f_death_state)
            if sfx_eat: sfx_eat.play()
            ai_bg_flash = 0.6
            ai_flash_color = ORANGE_LED
            ai_last_reward += 5000

        # AI ăn SF3
        if sf3_active and ai_x == sf3_x and ai_y == sf3_y:
            ai_length += SF3_LENGTH
            sf3_active = False
            f_death_state = food_agent.get_state((sf3_x, sf3_y), (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT)
            food_agent.learn("sf3", f_death_state, sf3_last_action, -100, f_death_state)
            if sfx_eat: sfx_eat.play()
            ai_bg_flash = 0.7
            ai_flash_color = WHITE
            ai_last_reward += 10000 # Ăn được mồi trắng là siêu phẩm

        if ai_bg_flash > 0:
            ai_bg_flash = max(0, ai_bg_flash - 0.02)

        # Logic spawn các loại mồi đặc biệt
        if not sf1_active and random.randint(1, SF1_RARITY) == 1:
            sf1_x, sf1_y = get_safe_food_pos(get_all_occupied_positions())
            sf1_active = True
        if not sf2_active and random.randint(1, SF2_RARITY) == 1:
            sf2_x, sf2_y = get_safe_food_pos(get_all_occupied_positions())
            sf2_active = True
        if not sf3_active and random.randint(1, SF3_RARITY) == 1:
            sf3_x, sf3_y = get_safe_food_pos(get_all_occupied_positions())
            sf3_active = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                dis = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                PAPER_TEXTURE = create_paper_texture()
                sync_entities_to_window()

            if event.type == pygame.KEYDOWN:
                if event.key in [pygame.K_p, pygame.K_ESCAPE] or event.key == getattr(pygame, 'K_AC_BACK', -1):
                    paused = True
                if event.key == pygame.K_m:
                    if sfx_click: sfx_click.play()
                    return False, snake_color_idx
                if event.key == pygame.K_k: # Nhấn K để đổi màu rắn
                    snake_color_idx = (snake_color_idx + 1) % len(SNAKE_COLORS)
                    if sfx_click: sfx_click.play()
                    bg_flash = 0.4
                    flash_color = SNAKE_COLORS[snake_color_idx]
            if event.type == pygame.MOUSEBUTTONDOWN:
                if pause_btn.collidepoint(event.pos):
                    paused = True
                if home_btn.collidepoint(event.pos):
                    if sfx_click: sfx_click.play()
                    return False, snake_color_idx
                
                # Lấy các vùng nút bấm ảo
                u, d, l, r, b = get_touch_rects()
                # Kiểm tra va chạm với điểm chạm tay (event.pos)
                if u.collidepoint(event.pos) and y1_change != SNAKE_BLOCK:
                    y1_change, x1_change = -SNAKE_BLOCK, 0
                elif d.collidepoint(event.pos) and y1_change != -SNAKE_BLOCK:
                    y1_change, x1_change = SNAKE_BLOCK, 0
                elif l.collidepoint(event.pos) and x1_change != SNAKE_BLOCK:
                    x1_change, y1_change = -SNAKE_BLOCK, 0
                elif r.collidepoint(event.pos) and x1_change != -SNAKE_BLOCK:
                    x1_change, y1_change = SNAKE_BLOCK, 0
                elif b.collidepoint(event.pos):
                    is_boosting = True
            if event.type == pygame.MOUSEBUTTONUP:
                is_boosting = False

            if event.type == pygame.KEYDOWN and not is_stunned:
                if event.key == pygame.K_LEFT and x1_change != SNAKE_BLOCK:
                    x1_change = -SNAKE_BLOCK
                    y1_change = 0
                elif event.key == pygame.K_RIGHT and x1_change != -SNAKE_BLOCK:
                    x1_change = SNAKE_BLOCK
                    y1_change = 0
                elif event.key == pygame.K_UP and y1_change != SNAKE_BLOCK:
                    y1_change = -SNAKE_BLOCK
                    x1_change = 0
                elif event.key == pygame.K_DOWN and y1_change != -SNAKE_BLOCK:
                    y1_change = SNAKE_BLOCK
                    x1_change = 0
                elif event.key == pygame.K_SPACE:
                    is_boosting = True
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    is_boosting = False

        if Length_of_snake - 1 >= SCORE_LIMIT and not game_close:
            end_reason = "BẠN ĐÃ CHIẾN THẮNG!"
            reason_color = GREEN_LED
            if sfx_win: sfx_win.play()
            game_stats.record_win()
            game_close = True
        if ai_length - 1 >= SCORE_LIMIT and not game_close:
            end_reason = "AI ĐẠT ĐIỂM GIỚI HẠN! BẠN THUA"
            reason_color = MAGENTA_LED
            if sfx_lose: sfx_lose.play()
            game_stats.record_loss()
            game_close = True
        if time_left <= 0 and not game_close:
            p_score = Length_of_snake - 1
            a_score = ai_length - 1
            if p_score > a_score:
                end_reason = "HẾT GIỜ! BẠN THẮNG!"
                reason_color = GREEN_LED
                if sfx_win: sfx_win.play()
                game_stats.record_win()
            elif a_score > p_score:
                end_reason = "HẾT GIỜ! AI THẮNG!"
                reason_color = MAGENTA_LED
                if sfx_lose: sfx_lose.play()
                game_stats.record_loss()
            else:
                end_reason = "HẾT GIỜ! HÒA NHAU!"
                reason_color = WHITE
                game_stats.record_draw()
            game_close = True
        new_x = x1 + x1_change
        new_y = y1 + y1_change
        if (new_x >= WIDTH or new_x < 0 or new_y >= HEIGHT or new_y < 0) and not is_stunned:
            if Length_of_snake > 1:
                Length_of_snake -= 1
                if new_x >= WIDTH: x1 -= SNAKE_BLOCK
                elif new_x < 0: x1 += SNAKE_BLOCK
                elif new_y >= HEIGHT: y1 -= SNAKE_BLOCK
                elif new_y < 0: y1 += SNAKE_BLOCK
                x1_change = 0
                y1_change = 0
                
                # Cập nhật ngay lập tức vị trí đầu rắn trong danh sách để hiển thị đúng khi bị choáng
                if snake_List:
                    snake_List[-1] = [x1, y1]

                is_boosting = False
                stun_until = pygame.time.get_ticks() + 1000
                # Hiệu ứng flash đỏ khi va chạm
                bg_flash = 0.4
                flash_color = RED_LED
                if sfx_hit: sfx_hit.play()
            else:
                if sfx_hit: sfx_hit.play()
                p_score = Length_of_snake - 1
                a_score = ai_length - 1
                if p_score > a_score:
                    end_reason = "VA CHẠM! BẠN VẪN THẮNG!"
                    reason_color = GREEN_LED
                    if sfx_win: sfx_win.play()
                    game_stats.record_win()
                elif a_score > p_score:
                    end_reason = "VA CHẠM! AI THẮNG ĐIỂM!"
                    reason_color = MAGENTA_LED
                    if sfx_lose: sfx_lose.play()
                    game_stats.record_loss()
                else:
                    end_reason = "VA CHẠM! AI THẮNG!"
                    reason_color = MAGENTA_LED
                    if sfx_lose: sfx_lose.play()
                    game_stats.record_loss()
                game_close = True
        else:
            x1 += x1_change
            y1 += y1_change

        # --- QUY TẮC CHIẾN ĐẤU: VA CHẠM THÂN ĐỐI PHƯƠNG ---
        # Nếu đầu người chơi chạm vào bất kỳ phần nào của AI (Trừ 5 điểm bạn, 2 điểm AI)
        if [x1, y1] in ai_snake_list:
            Length_of_snake = max(1, Length_of_snake - 5)
            ai_length = max(1, ai_length - 2)
            # Sửa lỗi visual: Thu ngắn danh sách đốt thân ngay lập tức
            while len(ai_snake_list) > ai_length: del ai_snake_list[0]
            while len(snake_List) > Length_of_snake: del snake_List[0]
            bg_flash = 0.5
            flash_color = RED_LED
            if sfx_hit: sfx_hit.play()

        # Nếu đầu AI chạm vào bất kỳ phần nào của người chơi (Trừ 5 điểm AI, 2 điểm bạn)
        if [ai_x, ai_y] in snake_List:
            ai_length = max(1, ai_length - 5)
            Length_of_snake = max(1, Length_of_snake - 2)
            # Sửa lỗi visual: Thu ngắn danh sách đốt thân ngay lập tức
            while len(ai_snake_list) > ai_length: del ai_snake_list[0]
            while len(snake_List) > Length_of_snake: del snake_List[0]
            ai_last_reward -= 400 # Phạt bộ não AI để nó học cách né thân người chơi
            ai_bg_flash = 0.5
            ai_flash_color = RED_LED
            if sfx_hit: sfx_hit.play()

        # Xử lý va chạm thức ăn TRƯỚC khi vẽ
        if x1 == foodx and y1 == foody:
            foodx, foody = get_safe_food_pos(get_all_occupied_positions())
            Length_of_snake += 1
            bg_flash = 0.3
            flash_color = GREEN_LED
            if sfx_eat: sfx_eat.play()

        # Người chơi ăn SF1
        if sf1_active and x1 == sf1_x and y1 == sf1_y:
            Length_of_snake += SF1_LENGTH
            sf1_active = False
            food_agent.learn("sf1", food_agent.get_state((sf1_x, sf1_y), (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT), sf1_last_action, -100, "death")
            bg_flash = 0.5
            flash_color = YELLOW_LED
            if sfx_eat: sfx_eat.play()
        # Người chơi ăn SF2
        if sf2_active and x1 == sf2_x and y1 == sf2_y:
            Length_of_snake += SF2_LENGTH
            sf2_active = False
            food_agent.learn("sf2", food_agent.get_state((sf2_x, sf2_y), (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT), sf2_last_action, -100, "death")
            bg_flash = 0.6
            flash_color = ORANGE_LED
            if sfx_eat: sfx_eat.play()
        # Người chơi ăn SF3
        if sf3_active and x1 == sf3_x and y1 == sf3_y:
            Length_of_snake += SF3_LENGTH
            sf3_active = False
            food_agent.learn("sf3", food_agent.get_state((sf3_x, sf3_y), (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT), sf3_last_action, -100, "death")
            bg_flash = 0.7
            flash_color = WHITE
            if sfx_eat: sfx_eat.play()

        # Giảm dần cường độ flash theo thời gian
        if bg_flash > 0:
            bg_flash = max(0, bg_flash - 0.02)

        # --- HỆ THỐNG DI CHUYỂN VÀ HỌC TẬP CỦA MỒI ĐẶC BIỆT ---
        food_directions = [(SNAKE_BLOCK, 0), (-SNAKE_BLOCK, 0), (0, SNAKE_BLOCK), (0, -SNAKE_BLOCK), (0, 0)]
        
        # Helper function for food movement and learning
        def move_and_learn_food(f_type, active, fx, fy, last_action, prev_dist_p, prev_dist_ai, move_chance, min_age_to_learn, weight, food_dirs):
            nonlocal x1, y1, ai_x, ai_y, snake_List, ai_snake_list

            if not active: return fx, fy, last_action, prev_dist_p, prev_dist_ai
            
            current_food_pos = (fx, fy)
            s_before = food_agent.get_state(current_food_pos, (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT)
            
            # Luôn cập nhật khoảng cách mới nhất để học tập chính xác
            new_dist_p = abs(fx - x1) + abs(fy - y1)
            new_dist_ai = abs(fx - ai_x) + abs(fy - ai_y)

            if random.randint(1, move_chance) != 1:
                # Nếu mồi không di chuyển, nó vẫn học dựa trên việc Rắn có tiến lại gần không
                dist_diff = (new_dist_p - prev_dist_p) + (new_dist_ai - prev_dist_ai)
                food_agent.learn(f_type, s_before, 4, dist_diff * weight, s_before)
                return fx, fy, 4, new_dist_p, new_dist_ai

            action_to_take = last_action # Default to last action
            if len(food_agent.q_table[f_type]) > min_age_to_learn:
                action_to_take = food_agent.choose_action(f_type, s_before)
            else:
                action_to_take = random.randint(0, 4)

            new_fx, new_fy = fx, fy
            if action_to_take < 4:
                dx, dy = food_dirs[action_to_take]
                temp_nx, temp_ny = fx + dx, fy + dy
                
                # Check for wall collision
                if 0 <= temp_nx < WIDTH and 0 <= temp_ny < HEIGHT:
                    # For SF3, also avoid snake bodies
                    if f_type == "sf3" and ([temp_nx, temp_ny] in snake_List or [temp_nx, temp_ny] in ai_snake_list):
                        pass # Don't move if it hits a body
                    else:
                        new_fx, new_fy = temp_nx, temp_ny
                else: # Hit a wall
                    food_agent.learn(f_type, s_before, action_to_take, -100 * weight, s_before) # Penalty for hitting wall

            s_after = food_agent.get_state((new_fx, new_fy), (x1, y1), (ai_x, ai_y), WIDTH, HEIGHT)
            
            # Reward for increasing distance from both snakes
            new_dist_p = abs(new_fx - x1) + abs(new_fy - y1)
            new_dist_ai = abs(new_fx - ai_x) + abs(new_fy - ai_y)
            
            # Thưởng mồi dựa trên sự thay đổi tổng khoảng cách tới kẻ săn đuổi
            dist_diff = (new_dist_p - prev_dist_p) + (new_dist_ai - prev_dist_ai)
            reward = dist_diff * weight + weight # Thưởng sinh tồn cực đậm
            
            food_agent.learn(f_type, s_before, action_to_take, reward, s_after)
            
            return new_fx, new_fy, action_to_take, new_dist_p, new_dist_ai

        # Apply movement and learning for each food type
        # SF1: Tăng động hơn một chút để người chơi dễ làm quen
        sf1_x, sf1_y, sf1_last_action, sf1_prev_dist_p, sf1_prev_dist_ai = move_and_learn_food("sf1", sf1_active, sf1_x, sf1_y, sf1_last_action, sf1_prev_dist_p, sf1_prev_dist_ai, 10, 0, 5, food_directions)
        # SF2: Di chuyển nhanh, học tập chuyên nghiệp hơn
        sf2_x, sf2_y, sf2_last_action, sf2_prev_dist_p, sf2_prev_dist_ai = move_and_learn_food("sf2", sf2_active, sf2_x, sf2_y, sf2_last_action, sf2_prev_dist_p, sf2_prev_dist_ai, 5, 50, 100, food_directions)
        # SF3: Di chuyển LIÊN TỤC, bộ não thiên tài (weight 2000), cực kỳ khó bắt
        sf3_x, sf3_y, sf3_last_action, sf3_prev_dist_p, sf3_prev_dist_ai = move_and_learn_food("sf3", sf3_active, sf3_x, sf3_y, sf3_last_action, sf3_prev_dist_p, sf3_prev_dist_ai, 1, 150, 2000, food_directions)
        
        dis.blit(PAPER_TEXTURE, (0, 0))

        draw_grid()

        # Vẽ các nút chức năng trên HUD
        pygame.draw.rect(dis, BLACK, pause_btn, 2)
        pygame.draw.rect(dis, BLACK, home_btn, 2)
        draw_text_prominent(dis, "||", font_style, BLACK, pause_btn.center)
        draw_text_prominent(dis, "M", font_style, BLACK, home_btn.center)

        pulse_food = abs(math.sin(pygame.time.get_ticks() * 0.01)) * 10
        food_rect = pygame.Rect(foodx, foody, SNAKE_BLOCK, SNAKE_BLOCK)
        draw_aura(dis, GREEN_LED, food_rect, spread=15 + int(pulse_food))
        pygame.draw.rect(dis, GREEN_LED, food_rect)

        # Vẽ SF1 (Vàng)
        if sf1_active:
            pulse_sf1 = abs(math.sin(pygame.time.get_ticks() * 0.015)) * 10
            sf1_rect = pygame.Rect(sf1_x, sf1_y, SNAKE_BLOCK, SNAKE_BLOCK)
            draw_aura(dis, YELLOW_LED, sf1_rect, spread=15 + int(pulse_sf1))
            pygame.draw.rect(dis, YELLOW_LED, sf1_rect)
        
        # Vẽ SF2 (Cam)
        if sf2_active:
            pulse_sf2 = abs(math.sin(pygame.time.get_ticks() * 0.018)) * 12
            sf2_rect = pygame.Rect(sf2_x, sf2_y, SNAKE_BLOCK, SNAKE_BLOCK)
            draw_aura(dis, ORANGE_LED, sf2_rect, spread=18 + int(pulse_sf2))
            pygame.draw.rect(dis, ORANGE_LED, sf2_rect)

        # Vẽ SF3 (Trắng)
        if sf3_active:
            pulse_sf3 = abs(math.sin(pygame.time.get_ticks() * 0.02)) * 15
            sf3_rect = pygame.Rect(sf3_x, sf3_y, SNAKE_BLOCK, SNAKE_BLOCK)
            draw_aura(dis, WHITE, sf3_rect, spread=20 + int(pulse_sf3))
            pygame.draw.rect(dis, WHITE, sf3_rect)

        current_pos = [x1, y1]
        if x1_change != 0 or y1_change != 0:
            snake_List.append(current_pos)
        while len(snake_List) > Length_of_snake:
            del snake_List[0]
        our_snake(SNAKE_BLOCK, snake_List, is_stunned, SNAKE_COLORS[snake_color_idx], flash_color, bg_flash, is_boosting)
        # Vẽ rắn AI với đầy đủ hiệu ứng Stun, Flash và Boosting
        our_snake(SNAKE_BLOCK, ai_snake_list, ai_is_stunned, MAGENTA_LED, ai_flash_color, ai_bg_flash, ai_is_boosting)

        # Vẽ các nút điều khiển ảo lên trên cùng
        if not game_close:
            draw_touch_controls(dis)

        draw_stats(Length_of_snake - 1, ai_length - 1, time_left, is_boosting)
        pygame.display.update()

        current_speed = BASE_SPEED
        if is_boosting or ai_is_boosting: # Tốc độ game tăng lên nếu bạn HOẶC AI tăng tốc
            current_speed *= BOOST_SPEED_MULTIPLIER
        clock.tick(current_speed)

def main():
    current_color = 0
    
    while True:
        res = main_menu(current_color)
        if res is not False:
            playing = True
            current_color = res
            while playing:
                playing, current_color = gameLoop(current_color)
                # Lưu dữ liệu ngay khi kết thúc một ván đấu
                ai_agent.save_data()
                food_agent.save_data()
                game_stats.save_stats()
        else:
            break
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
