import pygame, sys, random
from os import path

BLACK    = (0,   0,   0)
WHITE    = (255, 255, 255)
GRAY     = (120, 120, 140)
BG_COL   = (8,   8,   24)
LANE_A   = (18,  18,  40)
LANE_B   = (12,  12,  28)
SAFE_COL = (10,  40,  10)
GOAL_COL = (10,  70,  70)
HUD_COL  = (255, 220, 50)
LIVE_COL = (220, 60,  60)
BTN_AKT  = (40,  80,  160)    # pozadí aktivního tlačítka
BTN_NEA  = (20,  20,  45)     # pozadí neaktivního tlačítka
SEL_COL  = (160, 160, 190)    # text neaktivního tlačítka

WIDTH, HEIGHT = 800, 600
TILE          = 40
COLS          = WIDTH  // TILE   
ROWS          = HEIGHT // TILE  
FPS           = 60

START_COL    = COLS // 2
START_ROW    = ROWS - 1
ZIVOTY_START = 3
GRACE_PERIOD = 1500   # ms neporanitelnosti po zásahu

# Zdroj obrázků: kenney.nl/assets/space-shooter-remastered (licence součástí repozitáře)
LOD_SOUBORY  = ["lod_1.png", "lod_2.png", "lod_3.png", "lod_4.png"]
LOD_NAZVY    = ["Modrá",     "Červená",   "Zelená",    "Žlutá"]
METEOR_BIG   = "meteor_1.png"  
METEOR_SMALL = "meteor_2.png"   
ENEMY_FILE   = "nepritel.png"  
VYBUCH_FILE  = "vybuch.png"    
SPLASH_FILE  = "splash.png"     

PRUHY = [
    ( 1,  2.5, 0, 2),
    ( 2, -2.0, 1, 1),
    ( 3,  3.0, 0, 2),
    ( 4, -1.5, 1, 2),
    ( 5,  2.8, 0, 2),
    ( 6, -3.5, 1, 1),
    ( 7,  2.0, 0, 2),
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

#  Inicializace Pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Vesmírné Crossy Road")
clock = pygame.time.Clock()

ASSET_DIR = path.join(path.dirname(__file__), "assets")

def nacti_obrazek(nazev, sirka, vyska):
    """
    Načte PNG ze složky assets/ a přeškáluje na (sirka × vyska).
    Pokud soubor chybí, vrátí fialový placeholder – hra nekrachne.
    """
    soubor = path.join(ASSET_DIR, nazev)
    if path.exists(soubor):
        surf = pygame.image.load(soubor).convert_alpha()
        return pygame.transform.scale(surf, (sirka, vyska))
    surf = pygame.Surface((sirka, vyska), pygame.SRCALPHA)
    surf.fill((200, 0, 200, 200))   # fialová = chybějící asset
    return surf

font_big   = pygame.font.SysFont(None, 72)
font_med   = pygame.font.SysFont(None, 42)
font_small = pygame.font.SysFont(None, 28)

#  Třídy spritů

class Lod(pygame.sprite.Sprite):
    """
    Vesmírná loď hráče.
    Pohybuje se skokově po logické mřížce – jedna klávesa = jeden krok.
    Rect v pixelech se přepočítává ze souřadnic mřížky metodou _sync_rect().
    """

    OBRAZKY  = []   # herní velikost (TILE-4 × TILE-4) – sdílené třídní atributy
    NAHLEDKY = []   # zvětšené pro settings screen (TILE*2 × TILE*2)

    @classmethod
    def nacti_vsechny(cls):
        """Načte obrázky všech lodí jednou před spuštěním smyčky."""
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
        Vzorec:  rect.x = grid_col × TILE + 3
                 rect.y = grid_row × TILE + 3
        Offset 3 px centruje Surface (36 px) uvnitř buňky (40 px): 3 + 34 + 3 = 40 ✓
        """
        self.rect.x = self.grid_col * TILE + 3
        self.rect.y = self.grid_row * TILE + 3

    def reset(self):
        """Vrátí loď na výchozí startovní pozici (střed spodního okraje)."""
        self.grid_col = START_COL
        self.grid_row = START_ROW
        self._sync_rect()

    def move(self, d_col, d_row):
        """
        Posune loď o jeden krok v mřížce; pohyb je zastaven na okrajích.
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
        pass   # pohyb řídí KEYDOWN eventy


class Prekazka(pygame.sprite.Sprite):
    """
    Letící překážka – meteorit (typ 0) nebo trosky satelitu (typ 1).
    Obrázky se načítají jednou do sdílené cache (_cache).
    """

    _cache = {} 

    @classmethod
    def _ziskej(cls, nazev, w, h):
        """Vrátí Surface z cache nebo načte a uloží nový."""
        klic = (nazev, w, h)
        if klic not in cls._cache:
            cls._cache[klic] = nacti_obrazek(nazev, w, h)
        return cls._cache[klic]

    def __init__(self, radek, rychlost, typ):
        pygame.sprite.Sprite.__init__(self)
        self.rychlost = rychlost  

        if typ == 0:
            nazev      = random.choice([METEOR_BIG, METEOR_SMALL])
            self.image = Prekazka._ziskej(nazev, 34, 30)
        else:
            self.image = Prekazka._ziskej(ENEMY_FILE, 48, 36)

        self.rect = self.image.get_rect()
        w = self.rect.width  

        # Rovnoměrné rozložení přes celou šířku od začátku hry
        if rychlost > 0:
            self.rect.x = random.randint(-w, WIDTH)
        else:
            self.rect.x = random.randint(0, WIDTH + w)

        # Svislé umístění: střed překážky = střed řádku mřížky
        # Vzorec: centery = index_řádku × TILE + TILE // 2
        self.rect.centery = radek * TILE + TILE // 2

        # Přesná plovoucí X-pozice – rect.x je int, float zabraňuje sekání při nízké rychlosti
        self.pos_x = float(self.rect.x)

    def update(self, speed_mult=1.0):
        """
        Pohyb překážky: pos_x += rychlost × speed_mult.
        speed_mult se zvyšuje s každým levelem.
        Po opuštění obrazovky se objekt přesune na opačnou stranu s náhodným offsetem.
        """
        self.pos_x += self.rychlost * speed_mult

        if self.rychlost > 0 and self.pos_x > WIDTH + self.rect.width:
            self.pos_x = -self.rect.width - random.randint(10, 130)
        elif self.rychlost < 0 and self.pos_x < -self.rect.width:
            self.pos_x = WIDTH + random.randint(10, 130)

        self.rect.x = int(self.pos_x)


class Vybuch(pygame.sprite.Sprite):
    """
    Efekt výbuchu na místě zásahu lodi.
    Zobrazí se okamžitě a po 500 ms se sám odstraní metodou kill().
    """

    OBRAZEK = None   # sdílený obrázek – načte se při prvním výbuchu

    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        if Vybuch.OBRAZEK is None:
            Vybuch.OBRAZEK = nacti_obrazek(VYBUCH_FILE, TILE * 2, TILE * 2)
        self.image      = Vybuch.OBRAZEK
        self.rect       = self.image.get_rect(center=(x, y))
        self.cas_vzniku = pygame.time.get_ticks()

    def update(self):
        # kill() odstraní sprite ze všech skupin do kterých patří
        if pygame.time.get_ticks() - self.cas_vzniku > 500:
            self.kill()


#  Pomocné funkce

def generuj_hvezdy(pocet=130):
    """Vygeneruje seznam statických hvězd (x, y, polomer) – volá se jednou."""
    return [(random.randint(0, WIDTH),
             random.randint(0, HEIGHT),
             random.choice([1, 1, 1, 2]))
            for _ in range(pocet)]


def vytvor_prekazky(level=1):
    """
    Sestaví skupinu překážek pro daný level.
    Hustota: každé 2 levely přibyde o 1 překážka v každém pruhu.
    Rychlost řídí speed_mult za běhu – tato funkce ji neovlivňuje.
    """
    skupina = pygame.sprite.Group()
    bonus   = (level - 1) // 2   # +1 překážka za každé 2 dosažené levely
    for radek, rychlost, typ, pocet in PRUHY:
        for _ in range(pocet + bonus):
            skupina.add(Prekazka(radek, rychlost, typ))
    return skupina


def vykresli_pozadi(hvezdy):
    """Vykreslí barevné pruhy drah, jemné linky a hvězdy na pozadí."""
    screen.fill(BG_COL)
    for r in range(ROWS):
        pruh = pygame.Rect(0, r * TILE, WIDTH, TILE)
        if   r == 0:       pygame.draw.rect(screen, GOAL_COL, pruh)
        elif r == ROWS-1:  pygame.draw.rect(screen, SAFE_COL, pruh)
        elif r % 2 == 0:   pygame.draw.rect(screen, LANE_A,   pruh)
        else:              pygame.draw.rect(screen, LANE_B,   pruh)
    for r in range(1, ROWS):
        pygame.draw.line(screen, (35, 35, 65), (0, r * TILE), (WIDTH, r * TILE))
    for x, y, r in hvezdy:
        pygame.draw.circle(screen, WHITE, (x, y), r)


def vykresli_hud(skore, zivoty, level):
    """Zobrazí skóre vlevo, level uprostřed a ikony životů vpravo nahoře."""
    screen.blit(font_small.render(f"Skóre: {skore}", True, HUD_COL), (10, 8))
    lev = font_small.render(f"Level {level}", True, WHITE)
    screen.blit(lev, (WIDTH // 2 - lev.get_width() // 2, 8))
    for i in range(zivoty):
        cx = WIDTH - 20 - i * 26
        pygame.draw.polygon(screen, LIVE_COL, [(cx, 8), (cx + 9, 22), (cx - 9, 22)])


def vykresli_text_center(text, font, barva, y):
    """Vykreslí text horizontálně vycentrovaný na souřadnici Y."""
    surf = font.render(text, True, barva)
    screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))


def vykresli_tlacitko(text, rect, vybrano):
    """Vykreslí jedno menu tlačítko – zvýrazněné pokud je aktuálně vybráno."""
    pygame.draw.rect(screen, BTN_AKT if vybrano else BTN_NEA, rect, border_radius=8)
    pygame.draw.rect(screen, HUD_COL if vybrano else GRAY,    rect, 2, border_radius=8)
    surf = font_med.render(text, True, WHITE if vybrano else SEL_COL)
    screen.blit(surf, surf.get_rect(center=rect.center))


#  Předběžné načtení assetů 

Lod.nacti_vsechny()   # lodě načteme jednou - třídní atributy sdílejí všechny instance
hvezdy = generuj_hvezdy()

splash_img    = None
_splash_path  = path.join(ASSET_DIR, SPLASH_FILE)
if path.exists(_splash_path):
    splash_img = pygame.transform.scale(
        pygame.image.load(_splash_path).convert(), (WIDTH, HEIGHT)
    )

#  Herní proměnné

vybrana_lod = 0          # index aktivní lodi (0–3)
lod         = Lod(vybrana_lod)
hrac_grp    = pygame.sprite.Group(lod)
vybuch_grp  = pygame.sprite.Group()
prekazky    = vytvor_prekazky(1)

skore       = 0
zivoty      = ZIVOTY_START
level       = 1
speed_mult  = 1.0        # násobič rychlosti; +0.2 za každý dosažený level
cas_zasahu  = -9999      # čas posledního zásahu pro výpočet grace period

# Položky a rect objekty menu tlačítek (jednou, mimo smyčku)
MENU_POLOZKY = ["Hrát hru", "Nastavení", "Ukončit hru"]
menu_vyber   = 0
_bw, _bh     = 300, 56
_bx          = WIDTH // 2 - _bw // 2
TLACITKA     = [pygame.Rect(_bx, 305 + i * 74, _bw, _bh) for i in range(3)]

stav             = SPLASH
cas_splash_start = pygame.time.get_ticks()
SPLASH_TRVANI    = 5000   # ms; splash zmizí automaticky nebo po stisku klávesy

running = True

#  Hlavní herní smyčka   EVENT → UPDATE → RENDER

while running:

    # ── EVENT – zpracování fronty událostí 
    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        # Přeskočení splash – reaguje na klávesi i klik myši
        elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) and stav == SPLASH:
            stav = MENU

        elif event.type == pygame.KEYDOWN:

            # ── MENU: šipky navigují, ENTER vybírá
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
                        running = False

            # ── NASTAVENÍ: šipky volí loď, ENTER/ESC = zpět ─────────────────
            elif stav == SETTINGS:
                if event.key in (pygame.K_LEFT, pygame.K_UP):
                    vybrana_lod = (vybrana_lod - 1) % len(LOD_SOUBORY)
                elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    vybrana_lod = (vybrana_lod + 1) % len(LOD_SOUBORY)
                elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    stav = MENU

            # ── HRA: šipky pohybují lodí o jeden krok v mřížce ──────────────
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

                    # Dosažení horního okraje → bonus, nový level, více překážek
                    if dosahl_cile:
                        skore      += 50
                        level      += 1
                        speed_mult += 0.2           # překážky se každý level zrychlí
                        lod.reset()
                        prekazky = vytvor_prekazky(level)  # přidají se i nové překážky

            # ── GAME OVER: ENTER = zpět do menu
            elif stav == GAMEOVER:
                if event.key == pygame.K_RETURN:
                    stav = MENU

    # ── UPDATE – herní logika a pohyb

    if stav == SPLASH:
        # pygame.time.get_ticks() vrací ms od spuštění pygame.init()
        if pygame.time.get_ticks() - cas_splash_start > SPLASH_TRVANI:
            stav = MENU

    elif stav == PLAYING:
        prekazky.update(speed_mult)   
        hrac_grp.update()
        vybuch_grp.update()           # Vybuch.update() sám sebe odstraní po 500 ms

        nyni = pygame.time.get_ticks()
        if nyni - cas_zasahu > GRACE_PERIOD:   # kolize jen mimo dobu neporanitelnosti
            zasahy = pygame.sprite.spritecollide(lod, prekazky, False)
            if zasahy:
                zivoty    -= 1
                cas_zasahu = nyni   # spustí grace period
                # Výbuch na středu lodi v okamžiku zásahu
                vybuch_grp.add(Vybuch(lod.rect.centerx, lod.rect.centery))
                lod.reset()
                if zivoty <= 0:
                    stav = GAMEOVER

    # ── RENDER – vykreslování

    if stav == SPLASH:
        if splash_img:
            screen.blit(splash_img, (0, 0))
        else:
            screen.fill(BG_COL)
            for x, y, r in hvezdy:
                pygame.draw.circle(screen, WHITE, (x, y), r)
            vykresli_text_center("VESMÍRNÉ",          font_big, (60, 180, 255), HEIGHT // 2 - 85)
            vykresli_text_center("CROSSY ROAD",       font_big, (60, 180, 255), HEIGHT // 2 - 15)
            vykresli_text_center("Vesmírná záchranná mise", font_med, GRAY, HEIGHT // 2 + 60)
       

    elif stav == MENU:
        screen.fill(BG_COL)
        for x, y, r in hvezdy:
            pygame.draw.circle(screen, WHITE, (x, y), r)
        vykresli_text_center("VESMÍRNÉ CROSSY ROAD",    font_big,   (60, 180, 255), 65)
        vykresli_text_center("Vesmírná záchranná mise", font_small, GRAY,           148)
        for i, (text, rect) in enumerate(zip(MENU_POLOZKY, TLACITKA)):
            vykresli_tlacitko(text, rect, i == menu_vyber)
        vykresli_text_center("Šipky = výběr  |  ENTER = potvrdit", font_small, GRAY, HEIGHT - 32)

    elif stav == SETTINGS:
        screen.fill(BG_COL)
        for x, y, r in hvezdy:
            pygame.draw.circle(screen, WHITE, (x, y), r)
        vykresli_text_center("NASTAVENÍ",              font_big, HUD_COL, 48)
        vykresli_text_center("Výběr lod = Šipky",       font_med, WHITE,   132)

        # Čtyři náhledy lodí rovnoměrně rozmístěné
        nahled = TILE * 2   # 80 × 80 px
        mezera = 50
        celk_w = len(LOD_SOUBORY) * nahled + (len(LOD_SOUBORY) - 1) * mezera
        zac_x  = (WIDTH - celk_w) // 2

        for i, img in enumerate(Lod.NAHLEDKY):
            x    = zac_x + i * (nahled + mezera)
            rect = pygame.Rect(x, 205, nahled, nahled)
            zv   = (i == vybrana_lod)

            # Zvýrazňující rámeček kolem vybrané lodi
            pygame.draw.rect(screen,
                             HUD_COL if zv else (45, 45, 75),
                             rect.inflate(10, 10), 3, border_radius=6)
            screen.blit(img, rect)

            naz = font_small.render(LOD_NAZVY[i], True, HUD_COL if zv else GRAY)
            screen.blit(naz, naz.get_rect(centerx=rect.centerx, top=rect.bottom + 10))

        vykresli_text_center(f"Vybrána: {LOD_NAZVY[vybrana_lod]}", font_med, WHITE, 368)
        vykresli_text_center("ENTER nebo ESC = zpět do menu",       font_small, GRAY, HEIGHT - 32)

    elif stav == PLAYING:
        vykresli_pozadi(hvezdy)          # 1. pozadí + hvězdy
        prekazky.draw(screen)            # 2. překážky – Group.draw() hromadně
        hrac_grp.draw(screen)            # 3. loď nad překážkami
        vybuch_grp.draw(screen)          # 4. výbuchy nad vším ostatním

        # Blikání lodi
        nyni = pygame.time.get_ticks()
        if nyni - cas_zasahu < GRACE_PERIOD and (nyni // 100) % 2 == 1:
            blik = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            blik.fill((255, 255, 255, 90))
            screen.blit(blik, (lod.rect.x - 3, lod.rect.y - 3))

        vykresli_hud(skore, zivoty, level)   # 5. HUD 

    elif stav == GAMEOVER:
        screen.fill(BG_COL)
        for x, y, r in hvezdy:
            pygame.draw.circle(screen, WHITE, (x, y), r)
        vykresli_text_center("GAME OVER",                         font_big,   LIVE_COL, HEIGHT // 2 - 90)
        vykresli_text_center(f"Skóre: {skore}",                  font_med,   HUD_COL,  HEIGHT // 2 - 10)
        vykresli_text_center(f"Dosažený level: {level}",         font_small, WHITE,    HEIGHT // 2 + 50)
        vykresli_text_center("Stiskni ENTER pro návrat do menu", font_small, GRAY,     HEIGHT // 2 + 100)

    pygame.display.flip()   # přehodí double-buffer
    clock.tick(FPS)         # omezíní na max FPS

pygame.quit()
sys.exit()
