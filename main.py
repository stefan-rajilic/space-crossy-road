import pygame, sys, random
from os import path

#  Konstanty – barvy, rozměry, FPS

BLACK      = (0,   0,   0)
WHITE      = (255, 255, 255)
GRAY       = (120, 120, 140)
BG_COL     = (8,   8,   24)
LANE_A     = (18,  18,  40)
LANE_B     = (12,  12,  28)
SAFE_COL   = (10,  40,  10)
GOAL_COL   = (10,  70,  70)
OSTROV_COL = (15,  60,  30)    # bezpečný ostrůvek uprostřed mapy
HUD_COL    = (255, 220, 50)
LIVE_COL   = (220, 60,  60)
BTN_AKT    = (40,  80,  160)
BTN_NEA    = (20,  20,  45)
SEL_COL    = (160, 160, 190)

WIDTH, HEIGHT = 800, 600
TILE          = 40
COLS          = WIDTH  // TILE
ROWS          = HEIGHT // TILE
FPS           = 60

START_COL    = COLS // 2
START_ROW    = ROWS - 1
ZIVOTY_START = 3
GRACE_PERIOD = 1500
OSTROV_RADEK = 7        # řádek bezpečného ostrůvku – bez překážek

# Zdroj obrázků: kenney.nl/assets/space-shooter-remastered
LOD_SOUBORY  = ["lod_1.png", "lod_2.png", "lod_3.png", "lod_4.png"]
LOD_NAZVY    = ["Modrá",     "Červená",   "Zelená",    "Žlutá"]
METEOR_BIG   = "meteor_1.png"
METEOR_SMALL = "meteor_2.png"
ENEMY_FILE   = "nepritel.png"
VYBUCH_FILE  = "vybuch.png"     
SPLASH_FILE  = "splash.png"


# Pruhy překážek – řádek 7 (OSTROV_RADEK) záměrně chybí = bezpečná zóna
PRUHY = [
    ( 1,  2.5, 0, 2),
    ( 2, -2.0, 1, 1),
    ( 3,  3.0, 0, 2),
    ( 4, -1.5, 1, 2),
    ( 5,  2.8, 0, 2),
    ( 6, -3.5, 1, 1),
    # řádek 7 = OSTROV_RADEK – záměrně vynechán
    ( 8, -2.5, 1, 2),
    ( 9,  3.2, 0, 2),
    (10, -2.0, 1, 1),
    (11,  2.5, 0, 2),
    (12, -1.8, 1, 2),
    (13,  3.0, 0, 2),
]

# Herní stavy
SPLASH   = 0
MENU     = 1
SETTINGS = 2
PLAYING  = 3
GAMEOVER = 4
LEVEL_UP = 5    # krátká přechodová animace při dosažení cíle

#  Inicializace Pygame + mixer

pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Vesmírné Crossy Road")
clock = pygame.time.Clock()

ASSET_DIR = path.join(path.dirname(__file__), "assets")

def nacti_obrazek(nazev, sirka, vyska):
    """Načte PNG, přeškáluje. Chybějící soubor → fialový placeholder."""
    soubor = path.join(ASSET_DIR, nazev)
    if path.exists(soubor):
        surf = pygame.image.load(soubor).convert_alpha()
        return pygame.transform.scale(surf, (sirka, vyska))
    surf = pygame.Surface((sirka, vyska), pygame.SRCALPHA)
    surf.fill((200, 0, 200, 200))
    return surf

font_big   = pygame.font.SysFont(None, 72)
font_med   = pygame.font.SysFont(None, 42)
font_small = pygame.font.SysFont(None, 28)

#  High-score (uložení do souboru)

HS_FILE = path.join(path.dirname(__file__), "highscore.txt")

def nacti_highscore():
    try:
        with open(HS_FILE, 'r') as f:
            return int(f.read().strip())
    except Exception:
        return 0

def uloz_highscore(skore):
    """Zapíše nové skóre pouze pokud překonalo stávající rekord."""
    if skore > nacti_highscore():
        try:
            with open(HS_FILE, 'w') as f:
                f.write(str(skore))
        except Exception:
            pass

#  Třídy spritů

class Lod(pygame.sprite.Sprite):
    """
    Vesmírná loď hráče – pohybuje se skokově po mřížce.
    Obrázek se vybírá v nastavení (index 0–3).
    """

    OBRAZKY  = []   # herní velikost (TILE-4 × TILE-4)
    NAHLEDKY = []   # zvětšené náhledy pro settings screen

    @classmethod
    def nacti_vsechny(cls):
        """Načte všechny lodě jednou před spuštěním smyčky."""
        if cls.OBRAZKY:
            return
        for soubor in LOD_SOUBORY:
            img = nacti_obrazek(soubor, TILE - 4, TILE - 4)
            cls.OBRAZKY.append(img)
            cls.NAHLEDKY.append(pygame.transform.smoothscale(img, (TILE * 2, TILE * 2)))

    def __init__(self, index_lodi=0):
        pygame.sprite.Sprite.__init__(self)
        self.image    = Lod.OBRAZKY[index_lodi]
        self.rect     = self.image.get_rect()
        self.grid_col = START_COL
        self.grid_row = START_ROW
        self._sync_rect()

    def _sync_rect(self):
        """
        Přepočítá pixel-souřadnice rect ze souřadnic mřížky.
        Vzorec: rect.x = grid_col × TILE + 3
                rect.y = grid_row × TILE + 3
        Offset 3 px centruje Surface (36 px) v buňce (40 px).
        """
        self.rect.x = self.grid_col * TILE + 3
        self.rect.y = self.grid_row * TILE + 3

    def reset(self):
        """Vrátí loď na výchozí startovní pozici (střed dole)."""
        self.grid_col = START_COL
        self.grid_row = START_ROW
        self._sync_rect()

    def move(self, d_col, d_row):
        """
        Posune loď o jeden krok; pohyb je zastaven na okrajích.
        Vrátí (pohnul_se: bool, dosahl_cile: bool).
        """
        novy_col  = max(0, min(COLS - 1, self.grid_col + d_col))
        novy_row  = max(0, min(ROWS - 1, self.grid_row + d_row))
        pohnul_se = (novy_col != self.grid_col or novy_row != self.grid_row)
        self.grid_col = novy_col
        self.grid_row = novy_row
        self._sync_rect()
        return pohnul_se, pohnul_se and self.grid_row == 0

    def update(self):
        pass


class Prekazka(pygame.sprite.Sprite):
    """
    Letící překážka – meteorit (typ 0) nebo trosky satelitu (typ 1).
    Obrázky sdílí cache (_cache) mezi instancemi.
    Pohyb je float (pos_x) → plynulý i při nízké rychlosti.
    """

    _cache = {}

    @classmethod
    def _ziskej(cls, nazev, w, h):
        klic = (nazev, w, h)
        if klic not in cls._cache:
            cls._cache[klic] = nacti_obrazek(nazev, w, h)
        return cls._cache[klic]

    def __init__(self, radek, rychlost, typ):
        pygame.sprite.Sprite.__init__(self)
        self.rychlost = rychlost   # px/snímek; záporná = zprava doleva

        if typ == 0:
            nazev      = random.choice([METEOR_BIG, METEOR_SMALL])
            self.image = Prekazka._ziskej(nazev, 34, 30)
        else:
            self.image = Prekazka._ziskej(ENEMY_FILE, 48, 36)

        self.rect = self.image.get_rect()
        w = self.rect.width   # šířka po načtení – nutná pro výpočet X

        # Rovnoměrné rozložení přes celou šířku od začátku hry
        if rychlost > 0:
            self.rect.x = random.randint(-w, WIDTH)
        else:
            self.rect.x = random.randint(0, WIDTH + w)

        # Svislé umístění: centery = index_řádku × TILE + TILE // 2
        self.rect.centery = radek * TILE + TILE // 2
        self.pos_x = float(self.rect.x)

    def update(self, speed_mult=1.0):
        """Pohyb + zacyklení na opačné straně s náhodným offsetem."""
        self.pos_x += self.rychlost * speed_mult
        if self.rychlost > 0 and self.pos_x > WIDTH + self.rect.width:
            self.pos_x = -self.rect.width - random.randint(10, 130)
        elif self.rychlost < 0 and self.pos_x < -self.rect.width:
            self.pos_x = WIDTH + random.randint(10, 130)
        self.rect.x = int(self.pos_x)


class Vybuch(pygame.sprite.Sprite):
    """
    Animovaný efekt výbuchu.
    Načítá snímky vybuch_01.png – vybuch_07.png (fallback: vybuch.png).
    Po přehrání všech snímků se sprite odstraní metodou kill().
    """

    FRAMES       = None
    FRAME_TRVANI = 70   # ms na jeden snímek animace

    @classmethod
    def _nacti_frames(cls):
        frames = []
        for i in range(1, 8):
            soubor = path.join(ASSET_DIR, f"vybuch_{i:02d}.png")
            if path.exists(soubor):
                surf = pygame.image.load(soubor).convert_alpha()
                frames.append(pygame.transform.scale(surf, (TILE * 2, TILE * 2)))
        if not frames:
            frames = [nacti_obrazek(VYBUCH_FILE, TILE * 2, TILE * 2)]
        cls.FRAMES = frames

    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        if Vybuch.FRAMES is None:
            Vybuch._nacti_frames()
        self.snimek     = 0
        self.image      = Vybuch.FRAMES[0]
        self.rect       = self.image.get_rect(center=(x, y))
        self.cas_snimku = pygame.time.get_ticks()

    def update(self):
        nyni = pygame.time.get_ticks()
        if nyni - self.cas_snimku >= self.FRAME_TRVANI:
            self.snimek    += 1
            self.cas_snimku = nyni
            if self.snimek >= len(Vybuch.FRAMES):
                self.kill()   # odstraní sprite ze všech skupin
                return
            self.image = Vybuch.FRAMES[self.snimek]


#  Parallax hvězdy – dvě vrstvy s různou rychlostí

# Vzdálené hvězdy: menší, šedavé, pomalejší drift (pocit hloubky)
HVEZDY_FAR  = [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(70)]
# Blízké hvězdy: větší, bílé, rychlejší drift
HVEZDY_NEAR = [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(30)]

par_far_y  = 0.0   # akumulovaný Y-offset vzdálené vrstvy
par_near_y = 0.0   # akumulovaný Y-offset blízké vrstvy

#  Pomocné funkce

def kresli_hvezdy():
    """Vykreslí obě parallax vrstvy hvězd s aktuálními offsety."""
    for x, y in HVEZDY_FAR:
        dy = int((y + par_far_y) % HEIGHT)
        pygame.draw.circle(screen, (165, 165, 200), (x, dy), 1)
    for x, y in HVEZDY_NEAR:
        dy = int((y + par_near_y) % HEIGHT)
        pygame.draw.circle(screen, WHITE, (x, dy), 2)


def vytvor_prekazky(level=1):
    """
    Sestaví skupinu překážek pro daný level.
    Každé 2 levely přibyde o 1 překážka v každém pruhu.
    Rychlost se řídí speed_mult za běhu.
    """
    skupina = pygame.sprite.Group()
    bonus   = (level - 1) // 2
    for radek, rychlost, typ, pocet in PRUHY:
        for _ in range(pocet + bonus):
            skupina.add(Prekazka(radek, rychlost, typ))
    return skupina


def vykresli_pozadi():
    """Vykreslí barevné pruhy drah (včetně ostrůvku), linky a parallax hvězdy."""
    screen.fill(BG_COL)

    for r in range(ROWS):
        pruh = pygame.Rect(0, r * TILE, WIDTH, TILE)
        if   r == 0:             pygame.draw.rect(screen, GOAL_COL,   pruh)
        elif r == ROWS - 1:      pygame.draw.rect(screen, SAFE_COL,   pruh)
        elif r == OSTROV_RADEK:  pygame.draw.rect(screen, OSTROV_COL, pruh)
        elif r % 2 == 0:         pygame.draw.rect(screen, LANE_A,     pruh)
        else:                    pygame.draw.rect(screen, LANE_B,     pruh)

    # Zvýraznění hranic ostrůvku
    oy = OSTROV_RADEK * TILE
    pygame.draw.line(screen, (50, 160, 80), (0, oy),          (WIDTH, oy),          2)
    pygame.draw.line(screen, (50, 160, 80), (0, oy + TILE - 1), (WIDTH, oy + TILE - 1), 2)

    # Jemné linky oddělující pruhy
    for r in range(1, ROWS):
        pygame.draw.line(screen, (35, 35, 65), (0, r * TILE), (WIDTH, r * TILE))

    kresli_hvezdy()


def vykresli_trysky(lod):
    """
    Animované trysky pod lodí – 3 snímky střídané každých 80 ms.
    Kreslíme PŘED hrac_grp.draw() aby plamen byl vizuálně ZA lodí.
    """
    frame  = (pygame.time.get_ticks() // 80) % 3
    vel    = [10, 7, 13][frame]    # výška plamene
    sír    = [7,  5,  9][frame]    # šířka
    cx     = lod.rect.centerx
    cy     = lod.rect.bottom + 1
    # Vnější plamen – oranžový
    pygame.draw.ellipse(screen, (255, 110, 10), (cx - sír // 2, cy, sír, vel))
    # Vnitřní jádro – žlutobílé
    pygame.draw.ellipse(screen, (255, 230, 80), (cx - sír // 4, cy + 2, max(sír // 2, 2), vel // 2))


def vykresli_hud(skore, zivoty, level, highscore):
    """Skóre + rekord vlevo, level uprostřed, ikony životů vpravo."""
    screen.blit(font_small.render(f"Skóre: {skore}", True, HUD_COL), (10, 5))
    hs_barva = (100, 255, 100) if skore > 0 and skore >= highscore else GRAY
    screen.blit(font_small.render(f"Rekord: {highscore}", True, hs_barva), (10, 24))

    lev = font_small.render(f"Level {level}", True, WHITE)
    screen.blit(lev, (WIDTH // 2 - lev.get_width() // 2, 8))

    # Ikony životů – trojúhelníky ve tvaru lodi
    for i in range(zivoty):
        cx = WIDTH - 20 - i * 26
        pygame.draw.polygon(screen, LIVE_COL, [(cx, 8), (cx + 9, 22), (cx - 9, 22)])


def vykresli_text_center(text, font, barva, y):
    """Vykreslí text horizontálně vycentrovaný na souřadnici Y."""
    surf = font.render(text, True, barva)
    screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))


def vykresli_tlacitko(text, rect, vybrano):
    """Vykreslí menu tlačítko – zvýrazněné pokud je aktivní."""
    pygame.draw.rect(screen, BTN_AKT if vybrano else BTN_NEA, rect, border_radius=8)
    pygame.draw.rect(screen, HUD_COL if vybrano else GRAY,    rect, 2, border_radius=8)
    surf = font_med.render(text, True, WHITE if vybrano else SEL_COL)
    screen.blit(surf, surf.get_rect(center=rect.center))


#  Předběžné načtení assetů

Lod.nacti_vsechny()

splash_img   = None
_splash_path = path.join(ASSET_DIR, SPLASH_FILE)
if path.exists(_splash_path):
    splash_img = pygame.transform.scale(
        pygame.image.load(_splash_path).convert(), (WIDTH, HEIGHT)
    )


#  Herní proměnné

highscore   = nacti_highscore()
vybrana_lod = 0
lod         = Lod(vybrana_lod)
hrac_grp    = pygame.sprite.Group(lod)
vybuch_grp  = pygame.sprite.Group()
prekazky    = vytvor_prekazky(1)

skore       = 0
zivoty      = ZIVOTY_START
level       = 1
speed_mult  = 1.0
cas_zasahu  = -9999
level_up_cas = 0   # čas spuštění přechodové animace levelu

MENU_POLOZKY = ["Hrát hru", "Nastavení", "Ukončit hru"]
menu_vyber   = 0
_bw, _bh     = 300, 56
_bx          = WIDTH // 2 - _bw // 2
TLACITKA     = [pygame.Rect(_bx, 305 + i * 74, _bw, _bh) for i in range(3)]

stav             = SPLASH
cas_splash_start = pygame.time.get_ticks()
SPLASH_TRVANI    = 5000

running = True

#  Hlavní herní smyčka   EVENT → UPDATE → RENDER

while running:

    # EVENT – zpracování fronty událostí
    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            uloz_highscore(skore)
            running = False

        elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) and stav == SPLASH:
            stav = MENU

        elif event.type == pygame.KEYDOWN:

            # MENU 
            if stav == MENU:
                if event.key == pygame.K_UP:
                    menu_vyber = (menu_vyber - 1) % len(MENU_POLOZKY)
                elif event.key == pygame.K_DOWN:
                    menu_vyber = (menu_vyber + 1) % len(MENU_POLOZKY)
                elif event.key == pygame.K_RETURN:
                    if menu_vyber == 0:          # Hrát hru
                        skore      = 0
                        zivoty     = ZIVOTY_START
                        level      = 1
                        speed_mult = 1.0
                        cas_zasahu = -9999
                        lod        = Lod(vybrana_lod)
                        hrac_grp   = pygame.sprite.Group(lod)
                        vybuch_grp.empty()
                        prekazky   = vytvor_prekazky(level)
                        stav       = PLAYING
                    elif menu_vyber == 1:        # Nastavení
                        stav = SETTINGS
                    else:                        # Ukončit hru
                        uloz_highscore(skore)
                        running = False

            # NASTAVENÍ
            elif stav == SETTINGS:
                if event.key in (pygame.K_LEFT, pygame.K_UP):
                    vybrana_lod = (vybrana_lod - 1) % len(LOD_SOUBORY)
                elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    vybrana_lod = (vybrana_lod + 1) % len(LOD_SOUBORY)
                elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    stav = MENU

            # PLAYING – šipky = pohyb po mřížce
            elif stav == PLAYING:
                pohyb = None
                if event.key == pygame.K_UP:    pohyb = (0, -1)
                if event.key == pygame.K_DOWN:  pohyb = (0,  1)
                if event.key == pygame.K_LEFT:  pohyb = (-1, 0)
                if event.key == pygame.K_RIGHT: pohyb = ( 1, 0)

                if pohyb is not None:
                    pohnul_se, dosahl_cile = lod.move(*pohyb)

                    # +1 bod za každý skutečný krok nahoru
                    if pohyb[1] == -1 and pohnul_se:
                        skore += 1

                    # Dosažení horního okraje → přechod na nový level
                    if dosahl_cile:
                        skore        += 50
                        level        += 1
                        speed_mult   += 0.2
                        lod.reset()
                        prekazky      = vytvor_prekazky(level)
                        level_up_cas  = pygame.time.get_ticks()
                        stav = LEVEL_UP   # krátká animace přechodu

            # GAME OVER
            elif stav == GAMEOVER:
                if event.key == pygame.K_RETURN:
                    stav = MENU

    # UPDATE – herní logika

    # Parallax hvězdy scrollují vždy – dávají pocit pohybu i v menu
    par_far_y  = (par_far_y  + 0.15) % HEIGHT
    par_near_y = (par_near_y + 0.40) % HEIGHT

    if stav == SPLASH:
        # pygame.time.get_ticks() = ms od pygame.init(); po 5s přejde do menu
        if pygame.time.get_ticks() - cas_splash_start > SPLASH_TRVANI:
            stav = MENU

    elif stav == LEVEL_UP:
        # Hra je 1.5s pozastavena – přechodová animace přechodu levelu
        if pygame.time.get_ticks() - level_up_cas > 1500:
            stav = PLAYING

    elif stav == PLAYING:
        # Pohyb překážek – speed_mult předán do každé Prekazka.update()
        prekazky.update(speed_mult)
        hrac_grp.update()
        vybuch_grp.update()   # Vybuch se sám odstraní po přehrání snímků

        # Kolize – kontrolujeme jen mimo dobu neporanitelnosti (grace period)
        nyni = pygame.time.get_ticks()
        if nyni - cas_zasahu > GRACE_PERIOD:
            zasahy = pygame.sprite.spritecollide(lod, prekazky, False)
            if zasahy:
                zivoty    -= 1
                cas_zasahu = nyni
                vybuch_grp.add(Vybuch(lod.rect.centerx, lod.rect.centery))
                lod.reset()
                if zivoty <= 0:
                    uloz_highscore(skore)
                    highscore = nacti_highscore()
                    stav = GAMEOVER

    # RENDER – vykreslování

    if stav == SPLASH:
        if splash_img:
            screen.blit(splash_img, (0, 0))
        else:
            screen.fill(BG_COL)
            kresli_hvezdy()
            vykresli_text_center("VESMÍRNÉ",               font_big, (60, 180, 255), HEIGHT // 2 - 85)
            vykresli_text_center("CROSSY ROAD",            font_big, (60, 180, 255), HEIGHT // 2 - 15)
            vykresli_text_center("Vesmírná záchranná mise", font_med, GRAY,          HEIGHT // 2 + 58)
      
    elif stav == MENU:
        screen.fill(BG_COL)
        kresli_hvezdy()
        vykresli_text_center("VESMÍRNÉ CROSSY ROAD",    font_big,   (60, 180, 255), 65)
        vykresli_text_center("Vesmírná záchranná mise", font_small, GRAY,           148)
        if highscore > 0:
            vykresli_text_center(f"Rekord: {highscore}", font_small, HUD_COL, 180)
        for i, (text, rect) in enumerate(zip(MENU_POLOZKY, TLACITKA)):
            vykresli_tlacitko(text, rect, i == menu_vyber)
        vykresli_text_center("Šipky = výběr  |  ENTER = potvrdit", font_small, GRAY, HEIGHT - 32)

    elif stav == SETTINGS:
        screen.fill(BG_COL)
        kresli_hvezdy()
        vykresli_text_center("NASTAVENÍ",              font_big, HUD_COL, 48)
        vykresli_text_center("Výběr lodi – šipky", font_med, WHITE,  132)

        nahled = TILE * 2
        mezera = 50
        celk_w = len(LOD_SOUBORY) * nahled + (len(LOD_SOUBORY) - 1) * mezera
        zac_x  = (WIDTH - celk_w) // 2

        for i, img in enumerate(Lod.NAHLEDKY):
            x    = zac_x + i * (nahled + mezera)
            rect = pygame.Rect(x, 205, nahled, nahled)
            zv   = (i == vybrana_lod)
            pygame.draw.rect(screen,
                             HUD_COL if zv else (45, 45, 75),
                             rect.inflate(10, 10), 3, border_radius=6)
            screen.blit(img, rect)
            naz = font_small.render(LOD_NAZVY[i], True, HUD_COL if zv else GRAY)
            screen.blit(naz, naz.get_rect(centerx=rect.centerx, top=rect.bottom + 10))

        vykresli_text_center(f"Vybrána: {LOD_NAZVY[vybrana_lod]}", font_med, WHITE, 368)
        vykresli_text_center("ENTER nebo ESC = zpět do menu",       font_small, GRAY, HEIGHT - 32)

    elif stav == PLAYING:
        vykresli_pozadi()               # 1. pozadí + parallax hvězdy
        prekazky.draw(screen)           # 2. překážky
        vykresli_trysky(lod)            # 3. trysky plamene (za lodí)
        hrac_grp.draw(screen)           # 4. loď
        vybuch_grp.draw(screen)         # 5. výbuchy

        # Blikání lodi při grace period (každých 100 ms)
        nyni = pygame.time.get_ticks()
        if nyni - cas_zasahu < GRACE_PERIOD and (nyni // 100) % 2 == 1:
            blik = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            blik.fill((255, 255, 255, 90))
            screen.blit(blik, (lod.rect.x - 3, lod.rect.y - 3))

        vykresli_hud(skore, zivoty, level, highscore)   # 6. HUD navrchu

    elif stav == LEVEL_UP:
        # Herní scéna v pozadí (překážky jsou pozastaveny)
        vykresli_pozadi()
        prekazky.draw(screen)
        vykresli_trysky(lod)
        hrac_grp.draw(screen)

        # Bílý flash overlay – postupně mizí za 1.5s
        elapsed = pygame.time.get_ticks() - level_up_cas
        alpha   = max(0, int(230 * (1.0 - elapsed / 1500.0)))
        if alpha > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, alpha))
            screen.blit(overlay, (0, 0))

        vykresli_text_center(f"LEVEL {level}!",   font_big, HUD_COL, HEIGHT // 2 - 40)
        vykresli_hud(skore, zivoty, level, highscore)

    elif stav == GAMEOVER:
        screen.fill(BG_COL)
        kresli_hvezdy()
        vykresli_text_center("GAME OVER",                          font_big,   LIVE_COL,        HEIGHT // 2 - 108)
        vykresli_text_center(f"Skóre: {skore}",                   font_med,   HUD_COL,         HEIGHT // 2 - 32)
        if skore >= highscore and highscore > 0:
            vykresli_text_center("Nový rekord!",                   font_med,   (100, 255, 100), HEIGHT // 2 + 18)
        else:
            vykresli_text_center(f"Rekord: {highscore}",          font_small, GRAY,            HEIGHT // 2 + 18)
        vykresli_text_center(f"Dosažený level: {level}",          font_small, WHITE,           HEIGHT // 2 + 58)
        vykresli_text_center("Stiskni ENTER pro návrat do menu",  font_small, GRAY,            HEIGHT // 2 + 108)

    pygame.display.flip()   # přehodí double-buffer → zobrazí snímek
    clock.tick(FPS)         # omezí smyčku na max. FPS snímků/s

pygame.quit()
sys.exit()
