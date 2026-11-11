import pygame
import sys
import random
import math
import socket
import json
import threading

pygame.init()
WIDTH, HEIGHT = 1920, 1080   # resolución LÓGICA fija: todo el juego se dibuja a este tamaño


def _tamano_ventana_inicial():
    """Tamaño de ventana 16:9 que cabe en el escritorio (sin pasar de 1920x1080)."""
    try:
        dw, dh = pygame.display.get_desktop_sizes()[0]
    except Exception:
        info = pygame.display.Info()
        dw, dh = info.current_w, info.current_h
    escala = min(1.0, dw * 0.95 / WIDTH, dh * 0.88 / HEIGHT)
    return max(640, int(WIDTH * escala)), max(360, int(HEIGHT * escala))


pygame.display.set_mode(_tamano_ventana_inicial(), pygame.RESIZABLE)
# Lienzo donde se dibuja todo; actualizar_pantalla() lo escala a la ventana
screen = pygame.Surface((WIDTH, HEIGHT)).convert()

_buffer_escalado = None
_pantalla_completa = False


def actualizar_pantalla():
    """Escala el lienzo 1920x1080 a la ventana (con barras negras si la proporción no coincide)."""
    global _buffer_escalado
    ventana = pygame.display.get_surface()
    ww, wh = ventana.get_size()
    if (ww, wh) == (WIDTH, HEIGHT):
        ventana.blit(screen, (0, 0))
    else:
        escala = min(ww / WIDTH, wh / HEIGHT)
        nw, nh = max(1, int(WIDTH * escala)), max(1, int(HEIGHT * escala))
        if _buffer_escalado is None or _buffer_escalado.get_size() != (nw, nh):
            _buffer_escalado = pygame.Surface((nw, nh)).convert()
        if escala < 1.0:   # reducir: suavizado; ampliar: escalado rápido
            pygame.transform.smoothscale(screen, (nw, nh), _buffer_escalado)
        else:
            pygame.transform.scale(screen, (nw, nh), _buffer_escalado)
        ventana.fill((0, 0, 0))
        ventana.blit(_buffer_escalado, ((ww - nw) // 2, (wh - nh) // 2))
    pygame.display.flip()


def alternar_pantalla_completa():
    global _pantalla_completa
    try:
        _pantalla_completa = not _pantalla_completa
        if _pantalla_completa:
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            pygame.display.set_mode(_tamano_ventana_inicial(), pygame.RESIZABLE)
    except pygame.error:
        _pantalla_completa = not _pantalla_completa


def obtener_eventos():
    """pygame.event.get() + F11 para pantalla completa en cualquier pantalla del juego."""
    eventos = pygame.event.get()
    for e in eventos:
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
            alternar_pantalla_completa()
    return eventos

hud_iz = pygame.image.load("HUD/hub_iz.png").convert_alpha()
hud_dr = pygame.image.load("HUD/hub_dr.png").convert_alpha()

# Ajusta el tamaño al tamaño original o deseado si necesario
hud_iz = pygame.transform.scale(hud_iz, (520, 80))  # ejemplo
hud_dr = pygame.transform.scale(hud_dr, (520, 80))      # ejemplo

pygame.display.set_caption("Indie Nexus")
clock = pygame.time.Clock()

WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
BLACK = (0, 0, 0)
ORANGE = (255, 165, 0)
LIGHTBLUE = (0, 155, 255)
PURPLE = (148, 0, 211)

punch_sound = pygame.mixer.Sound("Sonidos/punch.wav")
victoria_sound = "Sonidos/victoria.wav" 

pygame.mixer.music.load("Sonidos/menus.wav") 
pygame.mixer.music.set_volume(0.5)  
pygame.mixer.music.play(-1)

player_width, player_height = 200, 300
gravity = 1
jump_strength = 20

# ---------------- Parámetros de combate (ajustables) ----------------
RONDAS_PARA_GANAR = 2        # mejor de 3
TIEMPO_RONDA_MS = 60000      # 60 s por ronda
INTRO_MS = 2000              # cuenta inicial ("RONDA n" y luego "FIGHT!")
INTRO_FIGHT_MS = 800         # últimos ms de la intro en los que se muestra "FIGHT!"
FIN_RONDA_MS = 2200          # pausa al terminar una ronda

ALCANCE_GOLPE = 50           # px de alcance extra delante del personaje (los cuerpos ya no se atraviesan)
KNOCKBACK_GOLPE = 14.0       # empuje al recibir un golpe (px/frame, decae solo)
KNOCKBACK_BLOQUEO = 6.0      # empuje al recibir un golpe cubriéndose
KNOCKBACK_FRICCION = 0.82
MAX_EMPUJE = 10.0            # máx. separación por frame cuando dos cuerpos se solapan

HITSTOP_GOLPE = 4            # frames de "congelado" al impactar
HITSTOP_BLOQUEO = 2
HITSTOP_KO = 10

GUARDIA_MAX = 100.0
GUARDIA_DRENAJE = 30.0       # por segundo mientras se cubre
GUARDIA_REGEN = 25.0         # por segundo cuando no se cubre
GUARDIA_RECUPERA = 35.0      # mínimo para volver a cubrirse tras romper la guardia
GUARDIA_COSTE_GOLPE = 2.0    # guardia que se pierde por cada punto de daño bloqueado

# La barra azul fina es la ESTAMINA: la gastan cubrirse y atacar
ATAQUE_COSTE_STAMINA = 20.0  # estamina que cuesta cada ataque (sin ella no se puede atacar)
KNOCKBACK_ATACANTE_GOLPE = 10.0    # el atacante también retrocede al conectar un golpe
KNOCKBACK_ATACANTE_BLOQUEO = 5.0   # ...y algo menos si el rival se cubrió

fondo_shovel = pygame.image.load("Escenarios/fuerte.jpg").convert_alpha()
fondo_shovel = pygame.transform.scale(fondo_shovel, (WIDTH, HEIGHT))
fondo_hollow = pygame.image.load("Escenarios/coliseo.jpg").convert_alpha()
fondo_hollow = pygame.transform.scale(fondo_hollow, (WIDTH, HEIGHT))
fondo_hollow_frente = pygame.image.load("Escenarios/coliseo_frente.jpg").convert_alpha()
fondo_hollow_frente = pygame.transform.scale(fondo_hollow_frente, (WIDTH, HEIGHT))
fondo_lava = pygame.image.load("Escenarios/lava.jpg").convert_alpha()
fondo_lava = pygame.transform.scale(fondo_lava, (WIDTH, HEIGHT))
fondo_panteon = pygame.image.load("Escenarios/panteon.jpg").convert_alpha()
fondo_panteon = pygame.transform.scale(fondo_panteon, (WIDTH, HEIGHT))
fondo_personajes = pygame.image.load("Seleccion/SeleccionPersonajes.png").convert_alpha()
fondo_personajes = pygame.transform.scale(fondo_personajes, (WIDTH, HEIGHT))
cuadro_negro = pygame.image.load("Seleccion/SeleccionPersonajesNegro.png").convert_alpha()
cuadro_negro = pygame.transform.scale(cuadro_negro, (WIDTH, HEIGHT))
cuadro_azul = pygame.image.load("Seleccion/SeleccionPersonajesAzul.png").convert_alpha()
cuadro_azul = pygame.transform.scale(cuadro_azul, (WIDTH, HEIGHT))
cuadro_rojo = pygame.image.load("Seleccion/SeleccionPersonajesRojo.png").convert_alpha()
cuadro_rojo = pygame.transform.scale(cuadro_rojo, (WIDTH, HEIGHT))


class Personaje:
    def __init__(self,nombre, x, y, width, height, color, velocidad=5, salto=20, gravedad=1, vida=100, vida_maxima = 100, ataque=10, sprite_path=None, tamaño_personalizado=None, animacion_frame_rate=10, animacion_frame_rate_parado = 10, animacion_frame_rate_ataque = 5, animacion_frame_rate_recibir = 1, animacion_frame_rate_salto = 1):
        self.nombre = nombre
        self.width, self.height = tamaño_personalizado if tamaño_personalizado else (width, height)
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.pos_x = float(self.rect.x)  # posición horizontal con decimales (para velocidades como 2.5)
        self.color = color
        self.velocidad_original = velocidad
        self.velocidad = velocidad
        self.salto = salto
        self.gravedad = gravedad
        self.y_vel = 0
        self.en_suelo = True
        self.vida = vida
        self.ataque = ataque
        self.recibiendo = False
        self.bloqueo = False
        self.recibir_timer = 0
        self.recibir_duracion = 300  # milisegundos
        self.sprite_path = sprite_path
        self.sprite = pygame.Surface((width, height))
        self.sprite.set_colorkey((0, 0, 0))
        self.sprite_estatico = None  # sprite quieto ya cargado (evita recargar del disco en cada frame)
        if sprite_path:
            self.sprite = pygame.image.load(sprite_path).convert_alpha()
            self.sprite = pygame.transform.scale(self.sprite, (self.width, self.height))
            self.sprite_estatico = self.sprite
        elif color is not None:  
            self.sprite.fill(color)
        
        self.bloqueo_sprites = []
        self.animacion_index_bloqueo = 0
        self.animacion_frame_counter_bloqueo = 0
        self.animacion_frame_rate_bloqueo = 5 
        self.bloqueo_sprites = [pygame.image.load(img).convert_alpha() for img in personajes_data[self.nombre].get("bloqueo_sprites", [])]
        self.victoria_sprites = []  # se cargan ya escaladas en crear_personaje()
        self.caminar_sprites = []
        self.parado_sprites = []
        self.ataque_sprites = []
        self.recibir_sprites = []
        self.salto_sprites = []
        self.animacion_index_salto = 0
        self.animacion_frame_counter_salto = 0
        self.saltando = False
        self.vida_maxima = vida_maxima  # CORREGIDO: antes estaba fijo en 100
        self.animacion_index = 0
        self.animacion_index_ataque = 0
        self.animacion_index_recibir = 0
        self.animacion_frame_rate = animacion_frame_rate  
        self.animacion_frame_counter = 0
        self.animacion_frame_rate_parado = animacion_frame_rate_parado
        self.animacion_frame_counter_recibir = 0
        self.animacion_frame_rate_recibir = animacion_frame_rate_recibir
        self.animacion_frame_counter_parado = 0
        self.animacion_frame_rate_ataque = animacion_frame_rate_ataque
        self.animacion_frame_rate_salto = animacion_frame_rate_salto
        self.animacion_frame_counter_ataque = 0
        self.animacion_index_parado = 0
        self.direccion = 1
        self.direccion_anterior = 1
        self.attacking = False
        self.attack_timer = 0
        self.spawn_x = x
        self.spawn_y = y
        self.direccion_inicial = 1
        self.golpe_aplicado = False
        self.frame_golpe = 1          # frame de la animación desde el que el golpe hace daño
        self.kb_x = 0.0               # velocidad de retroceso horizontal
        self.guardia = GUARDIA_MAX
        self.guardia_rota = False
        self.attack_cooldown = 500     

    def calcular_duracion_ataque(self):
        # Que el ataque dure al menos lo que dura su animación (a 60 FPS), mínimo 500 ms.
        if self.ataque_sprites:
            duracion_anim = int(len(self.ataque_sprites) * self.animacion_frame_rate_ataque * 1000 / 60) + 50
            self.attack_cooldown = max(500, duracion_anim)
            self.frame_golpe = max(1, len(self.ataque_sprites) // 2)

    # NOTA: el volteo (flip) según la dirección se hace UNA sola vez, en dibujar().
    # Por eso self.sprite siempre se guarda "mirando a la derecha".

    def mover(self, tecla_izquierda, tecla_derecha, keys=None):
        if self.attacking:
            return
        if keys is None:
            keys = pygame.key.get_pressed()
        moving = False

        # Movimiento lateral (se usa pos_x con decimales para que izquierda y derecha vayan igual de rápido)
        if keys[tecla_izquierda] and self.pos_x - self.velocidad > 0:
            self.pos_x -= self.velocidad
            self.direccion = -1
            moving = True
        if keys[tecla_derecha] and self.pos_x + self.velocidad + self.rect.width < WIDTH:
            self.pos_x += self.velocidad
            self.direccion = 1
            moving = True
        self.rect.x = int(self.pos_x + 0.5)

        # Animación de caminar
        if self.caminar_sprites and moving:
            self.animacion_frame_counter += 1
            if self.animacion_frame_counter >= self.animacion_frame_rate:
                self.animacion_frame_counter = 0
                self.animacion_index = (self.animacion_index + 1) % len(self.caminar_sprites)
            self.sprite = self.caminar_sprites[self.animacion_index]

        elif self.sprite_estatico is not None:
            self.sprite = self.sprite_estatico
        elif not moving:
            if self.caminar_sprites:
                self.sprite = self.caminar_sprites[0] if self.caminar_sprites else pygame.Surface((self.rect.width, self.rect.height))
                if self.caminar_sprites:
                    self.sprite.set_colorkey((0, 0, 0))
            else:
                self.sprite = pygame.Surface((self.rect.width, self.rect.height))
                if self.color:
                    self.sprite.fill(self.color)
                    self.sprite.set_colorkey((0, 0, 0))

        self.direccion_anterior = self.direccion

    
    def parado(self):
        if self.attacking:
            return
        if self.parado_sprites:
            self.animacion_frame_counter_parado += 1
            if self.animacion_frame_counter_parado >= self.animacion_frame_rate_parado:
                self.animacion_frame_counter_parado = 0
                self.animacion_index_parado = (self.animacion_index_parado + 1) % len(self.parado_sprites)
            self.sprite = self.parado_sprites[self.animacion_index_parado]
        self.direccion_anterior = self.direccion

    def saltar(self, tecla_salto, keys=None):
        if keys is None:
            keys = pygame.key.get_pressed()
        if keys[tecla_salto] and self.en_suelo:
            self.y_vel = -self.salto
            self.en_suelo = False
            self.saltando = True
            self.animacion_index_salto = 0
            self.animacion_frame_counter_salto = 0

    def aplicar_gravedad(self, escenario_actual):
        self.rect.y = int(self.rect.y + self.y_vel)
        if not self.en_suelo:
            self.y_vel += self.gravedad

        # Obtiene el nivel de suelo del escenario
        suelo_actual = niveles_suelo.get(escenario_actual, 670)  # Valor por defecto

        if self.rect.y >= suelo_actual:
            self.rect.y = suelo_actual
            self.y_vel = 0
            self.en_suelo = True

    def atacar(self, tecla_ataque, enemigo, keys=None):
        if keys is None:
            keys = pygame.key.get_pressed()
        
        if self.bloqueo:
            return False
        
        if keys[tecla_ataque] and not self.attacking:
            # Sin estamina suficiente no se puede atacar
            if self.guardia_rota or self.guardia < ATAQUE_COSTE_STAMINA:
                return False
            self.guardia -= ATAQUE_COSTE_STAMINA
            # El daño ya no se aplica al pulsar: se aplica en los frames activos
            # de la animación (ver comprobar_golpe)
            self.golpe_aplicado = False
            self.attacking = True
            self.attack_timer = pygame.time.get_ticks()
            self.animacion_index_ataque = 0
            self.animacion_frame_counter_ataque = 0
            return True
        return False
    
    def animar_ataque(self):
        if self.attacking and self.ataque_sprites:
            self.animacion_frame_counter_ataque += 1
            if self.animacion_frame_counter_ataque >= self.animacion_frame_rate_ataque:
                self.animacion_frame_counter_ataque = 0
                self.animacion_index_ataque += 1
                if self.animacion_index_ataque >= len(self.ataque_sprites):
                    self.attacking = False  # Fin del ataque
                    self.animacion_index_ataque = 0
                    return

            self.sprite = self.ataque_sprites[self.animacion_index_ataque % len(self.ataque_sprites)]

    def recibir(self, dano, direccion=0):
        bloqueando = self.bloqueo
        if bloqueando:
            self.guardia = max(0.0, self.guardia - dano * GUARDIA_COSTE_GOLPE)
            dano //= 2  # Reducir el daño a la mitad

        self.vida = max(0, self.vida - dano)
        # Retroceso en la dirección del golpe
        self.kb_x = direccion * (KNOCKBACK_BLOQUEO if bloqueando else KNOCKBACK_GOLPE)
        
        if bloqueando:
            if self.guardia <= 0:  # guardia rota: no puede cubrirse hasta recuperarla
                self.guardia_rota = True
                self.bloqueo = False
        else:  # Solo activar la animación de recibir si NO está bloqueando
            self.recibiendo = True
            self.recibir_timer = pygame.time.get_ticks()
            self.animacion_index_recibir = 0
            self.animacion_frame_counter_recibir = 0
            self.attacking = False  # un golpe recibido interrumpe su ataque
            self.golpe_aplicado = False

    def comprobar_golpe(self, enemigo):
        """Aplica el daño en los frames activos de la animación de ataque.
        Devuelve None, "golpe" o "bloqueado"."""
        if not self.attacking or self.golpe_aplicado or not self.ataque_sprites:
            return None
        if self.animacion_index_ataque < self.frame_golpe:
            return None
        delante = (enemigo.rect.centerx - self.rect.centerx) * self.direccion >= 0
        zona = self.rect.inflate(ALCANCE_GOLPE * 2, 0)
        if delante and zona.colliderect(enemigo.rect):
            self.golpe_aplicado = True
            bloqueado = enemigo.bloqueo
            enemigo.recibir(self.ataque, self.direccion)
            # Retroceso también para el atacante (en dirección contraria al golpe)
            self.kb_x = -self.direccion * (KNOCKBACK_ATACANTE_BLOQUEO if bloqueado else KNOCKBACK_ATACANTE_GOLPE)
            return "bloqueado" if bloqueado else "golpe"
        return None

    def aplicar_retroceso(self):
        if abs(self.kb_x) > 0.5:
            self.pos_x += self.kb_x
            self.pos_x = max(0.0, min(self.pos_x, WIDTH - self.rect.width))
            self.rect.x = int(self.pos_x + 0.5)
            self.kb_x *= KNOCKBACK_FRICCION
        else:
            self.kb_x = 0.0

    def actualizar_guardia(self, dt_ms):
        seg = dt_ms / 1000.0
        if self.bloqueo:
            self.guardia -= GUARDIA_DRENAJE * seg
            if self.guardia <= 0:
                self.guardia = 0.0
                self.guardia_rota = True
                self.bloqueo = False
        elif not self.attacking:  # atacando tampoco se recupera estamina
            self.guardia = min(GUARDIA_MAX, self.guardia + GUARDIA_REGEN * seg)
            if self.guardia_rota and self.guardia >= GUARDIA_RECUPERA:
                self.guardia_rota = False

    def reiniciar(self):
        """Deja al personaje listo para empezar una ronda."""
        self.vida = self.vida_maxima
        x = 100 if self.direccion_inicial == 1 else WIDTH - 100 - self.rect.width
        self.rect.x = x
        self.pos_x = float(x)
        self.rect.y = self.spawn_y
        self.y_vel = 0
        self.en_suelo = True
        self.saltando = False
        self.attacking = False
        self.golpe_aplicado = False
        self.recibiendo = False
        self.bloqueo = False
        self.kb_x = 0.0
        self.guardia = GUARDIA_MAX
        self.guardia_rota = False
        self.velocidad = self.velocidad_original
        self.direccion = self.direccion_inicial
        self.direccion_anterior = self.direccion_inicial
        self.animacion_index = 0
        self.animacion_index_parado = 0
        self.animacion_index_ataque = 0
        self.animacion_index_recibir = 0
        self.animacion_index_salto = 0
        self.animacion_index_bloqueo = 0
        if self.sprite_estatico is not None:
            self.sprite = self.sprite_estatico

    def actualizar_recibir(self, ahora):
        # El estado "recibiendo" termina SOLO por tiempo (recibir_duracion)
        if self.recibiendo and ahora - self.recibir_timer >= self.recibir_duracion:
            self.recibiendo = False

    def dibujar(self, pantalla):
        def blit_ajustado(sprite):
            if self.direccion == -1:
                sprite = pygame.transform.flip(sprite, True, False)
            ajuste_y = self.rect.bottom - sprite.get_height()
            pantalla.blit(sprite, (self.rect.x, ajuste_y))

        # Al dejar de cubrirse, la animación de bloqueo vuelve a empezar desde el primer frame
        if not self.bloqueo:
            self.animacion_index_bloqueo = 0
            self.animacion_frame_counter_bloqueo = 0

        if self.bloqueo and self.bloqueo_sprites:
            self.animacion_frame_counter_bloqueo += 1
            if self.animacion_frame_counter_bloqueo >= self.animacion_frame_rate_bloqueo:
                self.animacion_frame_counter_bloqueo = 0
                self.animacion_index_bloqueo += 1
                if self.animacion_index_bloqueo >= len(self.bloqueo_sprites):
                    self.animacion_index_bloqueo = len(self.bloqueo_sprites) - 1

            blit_ajustado(self.bloqueo_sprites[self.animacion_index_bloqueo])

        elif self.recibiendo and self.recibir_sprites:
            ultimo = len(self.recibir_sprites) - 1
            blit_ajustado(self.recibir_sprites[min(self.animacion_index_recibir, ultimo)])

            self.animacion_frame_counter_recibir += 1
            if self.animacion_frame_counter_recibir >= 6:
                self.animacion_frame_counter_recibir = 0
                self.animacion_index_recibir = min(self.animacion_index_recibir + 1, ultimo)

        elif self.attacking and self.saltando and self.ataque_sprites:
            blit_ajustado(self.ataque_sprites[self.animacion_index_ataque % len(self.ataque_sprites)])

        elif self.saltando and self.salto_sprites:
            ultimo = len(self.salto_sprites) - 1
            blit_ajustado(self.salto_sprites[min(self.animacion_index_salto, ultimo)])

            # Avanza la animación de salto (se queda en el último frame hasta aterrizar)
            self.animacion_frame_counter_salto += 1
            if self.animacion_frame_counter_salto >= self.animacion_frame_rate_salto:
                self.animacion_frame_counter_salto = 0
                if self.animacion_index_salto < ultimo:
                    self.animacion_index_salto += 1

        else:
            blit_ajustado(self.sprite)



fondos_escenarios = {
    "Fuerte de Pridemoor": fondo_shovel,
    "Coliseo de los Insensatos": fondo_hollow,
    "Mundo de lava": fondo_lava,
    "Tumba de la misericordia": fondo_panteon,
}

FONT = pygame.font.Font('Letra/KarmaFuture.ttf', 24)
FONT2 = pygame.font.Font('Letra/KarmaFuture.ttf', 64)
TITULO = pygame.font.Font("Letra/titulos.ttf", 128)
TITULO2 = pygame.font.Font("Letra/resto.ttf", 128)
FONT_RED = pygame.font.SysFont("Arial", 30)  # textos del modo en línea (tildes, IPs y dos puntos seguros)


personajes_data = {
    "Penitente": {"sprite": "Penitente/penitente_p1.png", "color": ORANGE, "vida": 110, "vida_maxima": 120, "ataque": 10, "animacion_frame_rate": 10, "animacion_frame_rate_victoria": 11, "animacion_frame_rate_salto": 1, "animacion_frame_rate_parado": 12, "animacion_frame_rate_recibir": 1, "animacion_frame_rate_ataque": 3, "salto": 20, "velocidad": 5, "gravedad": 1, "tamaño_personalizado": (180, 280), 
                        "caminar_sprites": ["Penitente/caminando/penitente_caminando1.png",
                                            "Penitente/caminando/penitente_caminando2.png",
                                            "Penitente/caminando/penitente_caminando3.png",
                                            "Penitente/caminando/penitente_caminando4.png",
                                            "Penitente/caminando/penitente_caminando5.png",
                                            "Penitente/caminando/penitente_caminando6.png",
                                            "Penitente/caminando/penitente_caminando7.png",
                                            "Penitente/caminando/penitente_caminando8.png",],
                        "parado_sprites": ["Penitente/penitente_p1.png",
                                           "Penitente/penitente_p2.png",
                                           "Penitente/penitente_p3.png",
                                           "Penitente/penitente_p4.png",
                                           "Penitente/penitente_p5.png",
                                           "Penitente/penitente_p6.png",
                                           "Penitente/penitente_p7.png",
                                           "Penitente/penitente_p8.png",
                                           "Penitente/penitente_p9.png",
                                           "Penitente/penitente_p10.png",
                                           "Penitente/penitente_p11.png",
                                           "Penitente/penitente_p12.png",
                                           "Penitente/penitente_p13.png"],
                        "victoria_sprites": ["Penitente/penitente_a1.png",
                                         "Penitente/penitente_a2.png",
                                         "Penitente/penitente_a3.png",
                                         "Penitente/penitente_a4.png",
                                         "Penitente/penitente_a5.png",
                                         "Penitente/penitente_a6.png",
                                         "Penitente/penitente_a7.png",
                                         "Penitente/penitente_a8.png",
                                         "Penitente/penitente_a9.png",
                                         "Penitente/penitente_a10.png"],
                        "ataque_sprites": ["Penitente/penitente_a1.png",
                                         "Penitente/penitente_a2.png",
                                         "Penitente/penitente_a3.png",
                                         "Penitente/penitente_a4.png",
                                         "Penitente/penitente_a5.png",
                                         "Penitente/penitente_a6.png",
                                         "Penitente/penitente_a7.png",
                                         "Penitente/penitente_a8.png",
                                         "Penitente/penitente_a9.png",
                                         "Penitente/penitente_a10.png"],
                        "recibir_sprites": ["Penitente/golpeado.png"],
                        "salto_sprites": ["Penitente/penitente_s1.png",
                                          "Penitente/penitente_s2.png"],
                        "bloqueo_sprites": ["Penitente/cubrir.png"]},
    "Castle Crasher": {"sprite": "Castle Crashers/cc_parado1.png", "color": (100, 100, 100), "vida": 100, "vida_maxima": 100, "ataque": 12, "animacion_frame_rate": 4, "animacion_frame_rate_victoria": 5, "animacion_frame_rate_salto": 1, "animacion_frame_rate_parado": 12, "animacion_frame_rate_recibir": 1, "animacion_frame_rate_ataque": 6, "salto": 22, "velocidad": 5, "gravedad": 1, "tamaño_personalizado": (180, 340),
                       "caminar_sprites": ["Castle Crashers/cc_walk1.png",
                                         "Castle Crashers/cc_walk2.png",
                                         "Castle Crashers/cc_walk3.png",
                                         "Castle Crashers/cc_walk4.png"],
                       "victoria_sprites": ["Castle Crashers/cc_seleccion1.png",
                                           "Castle Crashers/cc_seleccion2.png",
                                           "Castle Crashers/cc_seleccion3.png",
                                           "Castle Crashers/cc_seleccion4.png",
                                           "Castle Crashers/cc_seleccion5.png"],
                       "parado_sprites": ["Castle Crashers/cc_parado1.png",
                                         "Castle Crashers/cc_parado2.png"],
                       "ataque_sprites": ["Castle Crashers/cc_atacando2.png",
                                         "Castle Crashers/cc_atacando3.png",
                                         "Castle Crashers/cc_atacando4.png",
                                         "Castle Crashers/cc_atacando5.png",
                                         "Castle Crashers/cc_atacando6.png"],
                       "recibir_sprites": ["Castle Crashers/cc_golpaeado.png"],
                       "salto_sprites": ["Castle Crashers/cc_salto.png"],
                       "bloqueo_sprites": ["Castle Crashers/cc_cubrir1.png",
                                           "Castle Crashers/cc_cubrir2.png"]},
    "Hollow Knight": {"sprite": "Vacio/hk_parado.png", "color": None, "vida": 80, "vida_maxima": 80, "ataque": 14, "animacion_frame_rate": 15, "animacion_frame_rate_salto": 1, "animacion_frame_rate_victoria": 8, "animacion_frame_rate_parado": 12, "animacion_frame_rate_recibir": 1, "animacion_frame_rate_ataque": 8, "salto": 25, "velocidad": 6, "gravedad": 1.2, "tamaño_personalizado": (180, 340), 
                      "caminar_sprites": ["Vacio/caminando1.png",
                                          "Vacio/caminando2.png",
                                          "Vacio/caminando3.png"],
                      "victoria_sprites": ["Vacio/seleccion_hollow.png",
                                           "Vacio/seleccion_hollow0.png",
                                           "Vacio/seleccion_hollow1.png",
                                           "Vacio/seleccion_hollow2.png"],
                      "parado_sprites": ["Vacio/hk_parado.png",
                                         "Vacio/hk_parado1.png"],
                      "ataque_sprites": ["Vacio/h_golpe1.png",
                                         "Vacio/h_golpe2.png",
                                         "Vacio/h_golpe3.png"],
                      "recibir_sprites": ["Vacio/recibir.png"],
                      "salto_sprites": ["Vacio/salto1.png"],
                      "bloqueo_sprites": ["Vacio/bloqueo.png"]},
    "Shovel Knight": {"sprite": "Shovel Knight/pala_parado.png", "color": None, "vida": 140, "vida_maxima": 140, "ataque": 8, "animacion_frame_rate": 5, "animacion_frame_rate_parado": 12, "animacion_frame_rate_salto": 10, "animacion_frame_rate_victoria": 16, "animacion_frame_rate_recibir": 1, "animacion_frame_rate_ataque": 10, "salto": 18, "velocidad": 4, "gravedad": 1, "tamaño_personalizado": (220, 330),
                      "caminar_sprites": ["Shovel Knight/pala_caminando1.png",
                                         "Shovel Knight/pala_caminando2.png",
                                         "Shovel Knight/pala_caminando3.png",
                                         "Shovel Knight/pala_caminando4.png",
                                         "Shovel Knight/pala_caminando5.png",
                                         "Shovel Knight/pala_caminando6.png"], 
                      "parado_sprites": ["Shovel Knight/pala_parado1.png",
                                         "Shovel Knight/pala_parado2.png"],
                      "victoria_sprites": ["Shovel Knight/shovellevantada1.png",
                                           "Shovel Knight/shovellevantada2.png"],
                      "ataque_sprites": ["Shovel Knight/ataque1.png",
                                         "Shovel Knight/ataque2.png",
                                         "Shovel Knight/ataque3.png"],
                      "recibir_sprites": ["Shovel Knight/LePegaronPobechito.png"],
                      "salto_sprites": ["Shovel Knight/saltar.png"],
                      "bloqueo_sprites": ["Castle Crashers/cc_cubrir1.png",
                                           "Castle Crashers/cc_cubrir2.png"]},
}

# Tamaños personalizados para sprites de victoria por personaje
victory_sprite_sizes = {
    "Shovel Knight": (407, 391),
    "Hollow Knight": (200, 250),
    "Castle Crasher": (180, 220),
    "Penitente": (407, 391),
}

niveles_suelo = {
    "Fuerte de Pridemoor": 650,
    "Coliseo de los Insensatos": 650,  
    "Mundo de lava": 600,  
    "Tumba de la misericordia": 580
}


def play_scene_music(scene_name):
    current_volume = pygame.mixer.music.get_volume()  # Mantener el volumen actual
    
    pygame.mixer.music.stop()
    
    if scene_name == "Coliseo de los Insensatos":
        pygame.mixer.music.load("Sonidos/coliseo.wav")
    elif scene_name == "Fuerte de Pridemoor":
        pygame.mixer.music.load("Sonidos/fuerte.wav")
    elif scene_name == "Mundo de lava":
        pygame.mixer.music.load("Sonidos/lava.wav")
    elif scene_name == "Tumba de la misericordia":
        pygame.mixer.music.load("Sonidos/tumba.wav")
    
    if current_volume > 0:
        pygame.mixer.music.play(-1)
    pygame.mixer.music.set_volume(current_volume)  # Restaurar el volumen


def play_menu_music():
    current_volume = pygame.mixer.music.get_volume()
    pygame.mixer.music.stop()
    pygame.mixer.music.load("Sonidos/menus.wav")
    pygame.mixer.music.set_volume(current_volume)
    pygame.mixer.music.play(-1)


# Caché de la animación de fondo de configuración (se usaba cargando 6 imágenes cada vez que se entraba)
_cache_fondo_config = {}

def cargar_fondo_configuracion():
    clave = (WIDTH, HEIGHT)
    if clave not in _cache_fondo_config:
        _cache_fondo_config.clear()
        _cache_fondo_config[clave] = [
            pygame.transform.scale(
                pygame.image.load(f"Configuracion/configuracion{i+1}.png").convert_alpha(), (WIDTH, HEIGHT)
            )
            for i in range(6)
        ]
    return _cache_fondo_config[clave]

    
iconos_personajes = {
    "Penitente": pygame.image.load("HUD/pn.png").convert_alpha(),
    "Shovel Knight": pygame.image.load("HUD/sv.png").convert_alpha(),
    "Castle Crasher": pygame.image.load("HUD/cc.png").convert_alpha(),
    "Hollow Knight": pygame.image.load("HUD/hk.png").convert_alpha(),
}

# ---------- Efectos de golpe (dibujados con formas, sin imágenes) ----------
efectos_golpe = []                  # chispas activas
fx = {"hitstop": 0, "shake": 0}     # frames restantes de congelado y de temblor de pantalla


def dibujar_efectos(pantalla):
    for ef in efectos_golpe:
        p = 1 - ef["t"] / ef["dur"]
        base = 12 + p * 38
        largo = 26 * (1 - p) + 6
        grosor = max(2, int((5 if ef["grande"] else 3) * (1 - p)) + 1)
        for k in range(8):
            ang = k * (2 * math.pi / 8) + 0.3
            c, sn = math.cos(ang), math.sin(ang)
            p1 = (ef["x"] + c * base, ef["y"] + sn * base)
            p2 = (ef["x"] + c * (base + largo), ef["y"] + sn * (base + largo))
            pygame.draw.line(pantalla, ef["color"], p1, p2, grosor)
        if p < 0.5:
            pygame.draw.circle(pantalla, WHITE, (int(ef["x"]), int(ef["y"])), int(20 * (1 - p * 2)) + 2)


def actualizar_efectos():
    for ef in efectos_golpe:
        ef["t"] -= 1
    efectos_golpe[:] = [ef for ef in efectos_golpe if ef["t"] > 0]
    if fx["shake"] > 0:
        fx["shake"] -= 1


def texto_grande(pantalla, texto, color=WHITE, y=None):
    surf = pygame.transform.rotozoom(FONT2.render(texto, True, color), 0, 1.6)
    sombra = pygame.transform.rotozoom(FONT2.render(texto, True, BLACK), 0, 1.6)
    x = WIDTH // 2 - surf.get_width() // 2
    if y is None:
        y = HEIGHT // 2 - surf.get_height() // 2 - 80
    pantalla.blit(sombra, (x + 4, y + 4))
    pantalla.blit(surf, (x, y))


def draw_window(escenario_seleccionado, jugador1, jugador2, nombre_p1, nombre_p2,
                tiempo_s=None, victorias=None, texto_central=None, shake=(0, 0), aviso=None, ping=None):
    screen.blit(fondos_escenarios[escenario_seleccionado], (0, 0))

    jugador1.dibujar(screen)
    jugador2.dibujar(screen)
    dibujar_efectos(screen)

    # Iconos
    icon_p1 = iconos_personajes.get(nombre_p1)
    icon_p2 = iconos_personajes.get(nombre_p2)

    if icon_p1:
        icon_scaled = pygame.transform.scale(icon_p1, (100, 64))  # Ajusta el tamaño
        screen.blit(icon_scaled, (85, 25))  # Posición sobre el HUD izquierdo

    if icon_p2:
        icon_scaled = pygame.transform.scale(icon_p2, (100, 64))
        screen.blit(icon_scaled, (WIDTH - 163, 25))  # Posición sobre el HUD derecho

    # --- HUDs decorativos (sin imagen de personaje) ---
    screen.blit(hud_iz, (70, 20))
    screen.blit(hud_dr, (WIDTH - 580, 20))

    # --- Nombres ---
    p1_text = FONT.render(nombre_p1, True, WHITE)
    p2_text = FONT.render(nombre_p2, True, WHITE)
    screen.blit(p1_text, (150, 90))  # HUD izquierdo
    screen.blit(p2_text, (WIDTH - 320, 90))  # HUD derecho

    # --- BARRAS DE VIDA (400x25) ---
    barra_ancho = 400
    barra_alto = 20

    # Vida jugador 1 (normal: izquierda a derecha)
    vida_ratio_p1 = max(jugador1.vida / jugador1.vida_maxima, 0)
    pygame.draw.rect(screen, RED, pygame.Rect(180, 50, int(barra_ancho * vida_ratio_p1), barra_alto))

    # Vida jugador 2 (inversa: derecha a izquierda)
    vida_ratio_p2 = max(jugador2.vida / jugador2.vida_maxima, 0)
    vida_ancho_p2 = int(barra_ancho * vida_ratio_p2)
    x_inicio_p2 = WIDTH - 570 + (barra_ancho - vida_ancho_p2)
    pygame.draw.rect(screen, BLUE, pygame.Rect(x_inicio_p2, 50, vida_ancho_p2, barra_alto))

    # --- BARRAS DE ESTAMINA (finas, debajo de la vida) ---
    # Gris = agotada, naranja = no alcanza para atacar, azul = puede atacar. La marca blanca es el coste de un ataque.
    marca = int(barra_ancho * ATAQUE_COSTE_STAMINA / GUARDIA_MAX)
    for jug, izquierda in ((jugador1, True), (jugador2, False)):
        ancho = int(barra_ancho * max(jug.guardia, 0) / GUARDIA_MAX)
        if jug.guardia_rota:
            color = (120, 120, 120)
        elif jug.guardia < ATAQUE_COSTE_STAMINA:
            color = (255, 160, 40)
        else:
            color = LIGHTBLUE
        if izquierda:
            pygame.draw.rect(screen, color, pygame.Rect(180, 73, ancho, 6))
            pygame.draw.rect(screen, WHITE, pygame.Rect(180 + marca, 71, 2, 10))
        else:
            pygame.draw.rect(screen, color, pygame.Rect(WIDTH - 570 + (barra_ancho - ancho), 73, ancho, 6))
            pygame.draw.rect(screen, WHITE, pygame.Rect(WIDTH - 570 + barra_ancho - marca - 2, 71, 2, 10))

    # --- Rondas ganadas (círculos) ---
    if victorias is not None:
        for lado in (0, 1):
            for i in range(RONDAS_PARA_GANAR):
                x = 170 + i * 30 if lado == 0 else WIDTH - 180 - i * 30
                if i < victorias[lado]:
                    pygame.draw.circle(screen, (255, 215, 0), (x, 140), 9)
                pygame.draw.circle(screen, WHITE, (x, 140), 9, 2)

    # --- Cronómetro ---
    if tiempo_s is not None:
        color_t = RED if tiempo_s <= 10 else WHITE
        t_surf = FONT2.render(str(tiempo_s), True, color_t)
        screen.blit(t_surf, (WIDTH // 2 - t_surf.get_width() // 2, 20))

    # Fondo frente especial si aplica
    if escenario_seleccionado == "Coliseo de los Insensatos":
        screen.blit(fondo_hollow_frente, (0, 0))

    if texto_central:
        texto_grande(screen, texto_central)

    if aviso:
        a_surf = FONT_RED.render(aviso, True, WHITE)
        a_sombra = FONT_RED.render(aviso, True, BLACK)
        ax = WIDTH // 2 - a_surf.get_width() // 2
        screen.blit(a_sombra, (ax + 2, HEIGHT - 78))
        screen.blit(a_surf, (ax, HEIGHT - 80))
    if ping is not None:
        p_surf = FONT_RED.render(f"PING {ping} ms", True, (120, 255, 120) if ping < 80 else ((255, 220, 90) if ping < 160 else (255, 90, 90)))
        screen.blit(p_surf, (WIDTH - p_surf.get_width() - 20, HEIGHT - 50))

    # Temblor de pantalla
    if shake != (0, 0):
        screen.scroll(shake[0], shake[1])

    actualizar_pantalla()


# Bloqueo global de ataque: mientras un jugador ataca, el otro no puede atacar
# (si ambos pulsan a la vez, solo golpea uno, elegido al azar)
attack_in_progress = False
attack_lock_timer = 0
ATTACK_LOCK_DURATION = 500  # ms


class TeclasVirtuales:
    """Imita a pygame.key.get_pressed() para que la CPU use el mismo código que un jugador."""
    def __init__(self, activas=()):
        self.activas = set(activas)

    def __getitem__(self, tecla):
        return tecla in self.activas


class ControlCPU:
    """IA sencilla para el Jugador 2: se acerca, ataca y a veces se cubre."""
    def __init__(self):
        self.bloqueo_hasta = 0
        self.rival_atacaba = False

    def teclas(self, yo, rival):
        activas = set()
        ahora = pygame.time.get_ticks()
        dx = rival.rect.centerx - yo.rect.centerx
        hacia = 1 if dx > 0 else -1
        tecla_hacia = pygame.K_RIGHT if hacia == 1 else pygame.K_LEFT
        hueco = abs(dx) - (yo.rect.width + rival.rect.width) / 2.0
        en_alcance = hueco <= ALCANCE_GOLPE * 0.8

        # Cuando el rival empieza a atacar, a veces se cubre un momento
        if rival.attacking and not self.rival_atacaba and en_alcance:
            if yo.nombre != "Shovel Knight" and not yo.guardia_rota and random.random() < 0.55:
                self.bloqueo_hasta = ahora + 450
        self.rival_atacaba = rival.attacking

        if ahora < self.bloqueo_hasta and not yo.attacking:
            activas.add(pygame.K_DOWN)
        elif not en_alcance:
            activas.add(tecla_hacia)
            if yo.en_suelo and hueco > 220 and random.random() < 0.004:
                activas.add(pygame.K_UP)
        elif yo.direccion != hacia:
            activas.add(tecla_hacia)  # se gira hacia el rival
        elif not yo.attacking and yo.guardia >= ATAQUE_COSTE_STAMINA and random.random() < 0.05:
            activas.add(pygame.K_KP1)
        return TeclasVirtuales(activas)


def procesar_jugador(jugador, rival, keys, k_izq, k_der, k_salto, k_ataque, k_bloqueo):
    global attack_in_progress, attack_lock_timer
    # Movimiento
    moviendo = False
    if keys[k_izq] or keys[k_der]:
        jugador.velocidad = jugador.velocidad_original / 2 if jugador.bloqueo else jugador.velocidad_original
        jugador.mover(k_izq, k_der, keys)
        moviendo = True

    jugador.saltar(k_salto, keys)

    # Ataque (solo si el otro jugador no está atacando en este momento)
    if keys[k_ataque] and not attack_in_progress:
        if jugador.atacar(k_ataque, rival, keys):
            attack_in_progress = True
            attack_lock_timer = pygame.time.get_ticks()

    # Bloqueo (no se puede cubrir mientras se ataca ni con la guardia rota)
    if keys[k_bloqueo] and jugador.nombre != "Shovel Knight" and not jugador.guardia_rota and not jugador.attacking:
        jugador.bloqueo = True
        jugador.velocidad = jugador.velocidad_original / 2
    else:
        jugador.bloqueo = False

    if not moviendo and not jugador.attacking:
        jugador.parado()


def mascara_teclado(keys):
    """Convierte el teclado local en una máscara de bits (acepta WASD y flechas)."""
    m = 0
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        m |= 1
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        m |= 2
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        m |= 4
    if keys[pygame.K_e] or keys[pygame.K_KP1] or keys[pygame.K_SPACE]:
        m |= 8
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        m |= 16
    return m


def mascara_a_teclas(m, izq, der, salto, ataque, bloqueo):
    activas = set()
    if m & 1:
        activas.add(izq)
    if m & 2:
        activas.add(der)
    if m & 4:
        activas.add(salto)
    if m & 8:
        activas.add(ataque)
    if m & 16:
        activas.add(bloqueo)
    return TeclasVirtuales(activas)


class ControlRemoto:
    """Dentro del anfitrión: representa al jugador que juega desde otro ordenador (Jugador 2)."""
    def __init__(self, red):
        self.red = red
        self.mascara = 0
        self.salio = False

    def actualizar(self):
        for m in self.red.recibir():
            t = m.get("t")
            if t == "in":
                self.mascara = int(m.get("m", 0))
            elif t == "ping":
                self.red.enviar({"t": "pong", "c": m.get("c")})
            elif t == "bye":
                self.salio = True

    def teclas(self, yo, rival):
        return mascara_a_teclas(self.mascara, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_KP1, pygame.K_DOWN)


def handle_keys(jugador1, jugador2, cpu=None, online=False):
    global attack_in_progress
    keys = pygame.key.get_pressed()
    if online:  # el anfitrión juega como Jugador 1 con WASD/flechas/espacio
        keys = mascara_a_teclas(mascara_teclado(keys), pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_e, pygame.K_s)
    keys2 = cpu.teclas(jugador2, jugador1) if cpu else keys

    # Liberar el bloqueo de ataque cuando pasa el tiempo
    if attack_in_progress and pygame.time.get_ticks() - attack_lock_timer > ATTACK_LOCK_DURATION:
        attack_in_progress = False

    # Cada jugador con sus teclas
    p1 = (jugador1, jugador2, keys,
          pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_e, pygame.K_s)
    p2 = (jugador2, jugador1, keys2,
          pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_KP1, pygame.K_DOWN)

    # Si ambos pulsan atacar en el mismo frame, el orden decide quién golpea:
    # se sortea para que no gane siempre el mismo jugador.
    orden = [p1, p2]
    if keys[pygame.K_e] and keys2[pygame.K_KP1]:
        random.shuffle(orden)

    for args in orden:
        procesar_jugador(*args)


def show_inicio():
    
    # Cargar animación de fondo (fuera del while)
    fondo_inicio = [
    pygame.transform.scale(
        pygame.image.load(f"Inicio/inicio{i+1}.png").convert_alpha(), (WIDTH, HEIGHT)
    )
    for i in range(49)
    ]
    
    fondo_anim_index = 0
    fondo_frame_counter = 0
    fondo_frame_rate = 16  # cambia cada 4 frames
    
    actualizar_pantalla()
    waiting = True
    while waiting:
         # Actualizar animación de fondo
        fondo_frame_counter += 1
        if fondo_frame_counter >= fondo_frame_rate:
            fondo_anim_index = (fondo_anim_index + 1) % len(fondo_inicio)
            fondo_frame_counter = 0

        # Dibujar fondo actual
        screen.blit(fondo_inicio[fondo_anim_index], (0, 0))   
        title = TITULO2.render("Indie Nexus", True, PURPLE)
        instruction = FONT.render("Presiona ENTER para comenzar", True, BLACK)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 400))
        screen.blit(instruction, (WIDTH // 2 - instruction.get_width() // 2, HEIGHT // 2))
        actualizar_pantalla()
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    waiting = False

def show_menu():
    selected = 0
    options = ["JUGAR", "VS CPU", "EN LINEA", "CONFIGURACION", "SALIR"]
    
    # Cargar animación de fondo (fuera del while)
    fondo_menu = [
    pygame.transform.scale(
        pygame.image.load(f"Menu/menu{i+1}.png").convert_alpha(), (WIDTH, HEIGHT)
    )
    for i in range(49)
    ]
    
    fondo_anim_index = 0
    fondo_frame_counter = 0
    fondo_frame_rate = 8  # cambia cada 4 frames
    
    
    while True:
        # Actualizar animación de fondo
        fondo_frame_counter += 1
        if fondo_frame_counter >= fondo_frame_rate:
            fondo_anim_index = (fondo_anim_index + 1) % len(fondo_menu)
            fondo_frame_counter = 0

        # Dibujar fondo actual
        screen.blit(fondo_menu[fondo_anim_index], (0, 0))
        for i, text in enumerate(options):
            color = RED if i == selected else WHITE
            rendered_text = FONT.render(text, True, color)
            screen.blit(rendered_text, (WIDTH // 2 - rendered_text.get_width() // 2, HEIGHT // 2 - 120 + i * 40))
        actualizar_pantalla()
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(options)
                elif event.key == pygame.K_RETURN:
                    if selected == 0:
                        return "JUGAR"
                    elif selected == 1:
                        return "CPU"
                    elif selected == 2:
                        return "ONLINE"
                    elif selected == 3:
                        show_config()
                    elif selected == 4:
                        pygame.quit()
                        sys.exit()

def registrar_impacto(atacante, victima, resultado):
    """Chispa + congelado + temblor al impactar un golpe."""
    inter = atacante.rect.inflate(ALCANCE_GOLPE * 2, 0).clip(victima.rect)
    x = inter.centerx
    y = victima.rect.top + int(victima.rect.height * 0.35)
    bloqueado = resultado == "bloqueado"
    ko = victima.vida <= 0
    efectos_golpe.append({"x": x, "y": y, "t": 10, "dur": 10,
                          "color": LIGHTBLUE if bloqueado else (255, 230, 90),
                          "grande": not bloqueado})
    fx["hitstop"] = max(fx["hitstop"], HITSTOP_KO if ko else (HITSTOP_BLOQUEO if bloqueado else HITSTOP_GOLPE))
    fx["shake"] = max(fx["shake"], 12 if ko else (4 if bloqueado else 8))


def resolver_colisiones(a, b):
    """Los cuerpos no se atraviesan cuando ambos están en el suelo (en el aire sí se puede saltar por encima)."""
    if not (a.en_suelo and b.en_suelo):
        return
    if not a.rect.colliderect(b.rect):
        return
    solape = min(a.rect.right, b.rect.right) - max(a.rect.left, b.rect.left)
    if solape <= 0:
        return
    izq, der = (a, b) if a.rect.centerx <= b.rect.centerx else (b, a)
    quiere = min(solape / 2.0, MAX_EMPUJE)
    margen_izq = max(0.0, izq.pos_x)
    margen_der = max(0.0, WIDTH - der.rect.width - der.pos_x)
    mov_izq = min(quiere, margen_izq)
    mov_der = min(quiere, margen_der)
    falta = 2 * quiere - (mov_izq + mov_der)
    if falta > 0:  # si uno está contra la pared, el otro cede lo que falta
        extra = min(falta, margen_izq - mov_izq)
        mov_izq += extra
        falta -= extra
        extra = min(falta, margen_der - mov_der)
        mov_der += extra
    izq.pos_x -= mov_izq
    der.pos_x += mov_der
    for p in (izq, der):
        p.rect.x = int(p.pos_x + 0.5)


def actualizar_fisica(escenario, jugador1, jugador2, ahora):
    for j in (jugador1, jugador2):
        j.aplicar_gravedad(escenario)
        if j.en_suelo:
            j.saltando = False
        j.aplicar_retroceso()
    resolver_colisiones(jugador1, jugador2)
    for j in (jugador1, jugador2):
        if j.attacking and ahora - j.attack_timer > j.attack_cooldown:
            j.attacking = False
        j.animar_ataque()


def desplazar_timers(jugador1, jugador2, ms):
    """Mantiene los temporizadores en 'tiempo de juego' durante congelados y pausas."""
    global attack_lock_timer
    for j in (jugador1, jugador2):
        j.attack_timer += ms
        j.recibir_timer += ms
    attack_lock_timer += ms


def pausar():
    """Menú de pausa. Devuelve (accion, ms_transcurridos); accion = 'continuar' o 'menu'."""
    inicio = pygame.time.get_ticks()
    pygame.mixer.music.pause()
    fondo_pausa = screen.copy()
    velo = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    velo.fill((0, 0, 0, 170))
    opciones = ["CONTINUAR", "SALIR AL MENU"]
    sel = 0
    accion = None
    while accion is None:
        screen.blit(fondo_pausa, (0, 0))
        screen.blit(velo, (0, 0))
        titulo = FONT2.render("PAUSA", True, WHITE)
        screen.blit(titulo, (WIDTH // 2 - titulo.get_width() // 2, HEIGHT // 2 - 180))
        for i, texto in enumerate(opciones):
            color = RED if i == sel else WHITE
            t = FONT.render(texto, True, color)
            screen.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 40 + i * 50))
        actualizar_pantalla()
        clock.tick(30)
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    accion = "continuar"
                elif event.key == pygame.K_UP:
                    sel = (sel - 1) % len(opciones)
                elif event.key == pygame.K_DOWN:
                    sel = (sel + 1) % len(opciones)
                elif event.key == pygame.K_RETURN:
                    accion = "continuar" if sel == 0 else "menu"
    pygame.mixer.music.unpause()
    clock.tick()  # evita un salto de tiempo al volver
    return accion, pygame.time.get_ticks() - inicio


def jugar_ronda(escenario, jugador1, jugador2, nombre1, nombre2, ronda, victorias, cpu, red=None):
    """Juega una ronda. Devuelve ('ko', idx_ganador), ('tiempo', idx_ganador o None) o ('menu', None)."""
    global attack_in_progress
    jugador1.reiniciar()
    jugador2.reiniciar()
    attack_in_progress = False
    efectos_golpe.clear()
    fx["hitstop"] = 0
    fx["shake"] = 0

    fase = "intro"
    fase_ms = INTRO_MS
    tiempo_ms = TIEMPO_RONDA_MS
    resultado = None
    texto = None
    salir_hasta = 0
    clock.tick()  # reinicia el contador de dt

    while True:
        dt = min(clock.tick(60), 50)

        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if red:  # online no hay pausa: ESC dos veces para abandonar
                    if pygame.time.get_ticks() < salir_hasta:
                        red.enviar({"t": "bye"})
                        red.cerrar()
                        return "menu", None
                    salir_hasta = pygame.time.get_ticks() + 2000
                else:
                    accion, ms = pausar()
                    if accion == "menu":
                        play_menu_music()
                        return "menu", None
                    desplazar_timers(jugador1, jugador2, ms)
        ahora = pygame.time.get_ticks()

        if red:
            cpu.actualizar()
            if cpu.salio:
                red._caer("El rival abandonó la partida", True)
            if not red.conectado:
                mensaje_bloqueante(red.motivo)
                return "menu", None

        # --- Congelado al impactar (hit-stop): solo se redibuja ---
        if fx["hitstop"] > 0:
            fx["hitstop"] -= 1
            desplazar_timers(jugador1, jugador2, dt)
        elif fase == "intro":
            fase_ms -= dt
            for j in (jugador1, jugador2):
                j.actualizar_recibir(ahora)
                j.aplicar_gravedad(escenario)
                if j.en_suelo:
                    j.saltando = False
                j.parado()
            texto = f"RONDA {ronda}" if fase_ms > INTRO_FIGHT_MS else "FIGHT!"
            if fase_ms <= 0:
                fase = "pelea"
                texto = None
        elif fase == "pelea":
            tiempo_ms -= dt
            jugador1.actualizar_recibir(ahora)
            jugador2.actualizar_recibir(ahora)
            handle_keys(jugador1, jugador2, cpu, online=bool(red))
            jugador1.actualizar_guardia(dt)
            jugador2.actualizar_guardia(dt)
            actualizar_fisica(escenario, jugador1, jugador2, ahora)

            # El daño se aplica en los frames activos de cada ataque
            for atacante, victima in ((jugador1, jugador2), (jugador2, jugador1)):
                res = atacante.comprobar_golpe(victima)
                if res:
                    punch_sound.play()
                    red_info["golpes"] += 1
                    registrar_impacto(atacante, victima, res)

            if jugador1.vida <= 0 or jugador2.vida <= 0:
                if jugador1.vida <= 0 and jugador2.vida <= 0:
                    resultado = ("ko", None)
                    texto = "EMPATE"
                else:
                    resultado = ("ko", 1 if jugador1.vida <= 0 else 0)
                    texto = "KO!"
                fase = "fin"
            elif tiempo_ms <= 0:
                r1 = jugador1.vida / jugador1.vida_maxima
                r2 = jugador2.vida / jugador2.vida_maxima
                if r1 > r2:
                    resultado, texto = ("tiempo", 0), "TIEMPO!"
                elif r2 > r1:
                    resultado, texto = ("tiempo", 1), "TIEMPO!"
                else:
                    resultado, texto = ("tiempo", None), "EMPATE"
                fase = "fin"
            if fase == "fin":
                fase_ms = FIN_RONDA_MS
                for j in (jugador1, jugador2):
                    j.attacking = False
                    j.bloqueo = False
        else:  # fase == "fin": nadie controla, solo cae/rebota y espera
            fase_ms -= dt
            for j in (jugador1, jugador2):
                j.actualizar_recibir(ahora)
            actualizar_fisica(escenario, jugador1, jugador2, ahora)
            for j in (jugador1, jugador2):
                j.parado()
            if fase_ms <= 0:
                return resultado

        # --- Dibujo ---
        tiempo_s = max(0, math.ceil(tiempo_ms / 1000.0))
        if red:  # el invitado recibe este estado y lo dibuja
            red.enviar(construir_snapshot(jugador1, jugador2, tiempo_s, victorias, texto), descartable=True)
        amp = fx["shake"] // 2 + 1 if fx["shake"] > 0 else 0
        sh = (random.randint(-amp, amp), random.randint(-amp, amp)) if amp else (0, 0)
        aviso = "Pulsa ESC otra vez para abandonar la partida" if (red and pygame.time.get_ticks() < salir_hasta) else None
        draw_window(escenario, jugador1, jugador2, nombre1, nombre2,
                    tiempo_s=tiempo_s, victorias=victorias,
                    texto_central=texto, shake=sh, aviso=aviso)
        if fx["hitstop"] == 0:
            actualizar_efectos()


def jugar_partida(escenario, jugador1, jugador2, nombre1, nombre2, vs_cpu=False, red=None):
    """Mejor de 3 rondas. Devuelve 'menu' o 'revancha'."""
    victorias = [0, 0]
    ronda = 1
    cpu = ControlCPU() if vs_cpu else (ControlRemoto(red) if red else None)
    while True:
        res = jugar_ronda(escenario, jugador1, jugador2, nombre1, nombre2, ronda, victorias, cpu, red)
        if res[0] == "menu":
            return "menu"
        idx = res[1]
        if idx is None:  # empate: se repite la ronda
            continue
        victorias[idx] += 1
        if victorias[idx] >= RONDAS_PARA_GANAR:
            nombre = nombre1 if idx == 0 else nombre2
            obj = jugador1 if idx == 0 else jugador2
            if red:
                red.enviar({"t": "ganador", "idx": idx})
            return show_winner(nombre, obj, fondos_escenarios[escenario], red)
        ronda += 1


def run_game(escenario_seleccionado, jugador1, jugador2, nombre_personaje1, nombre_personaje2, vs_cpu=False, red=None):
    while True:
        resultado = jugar_partida(escenario_seleccionado, jugador1, jugador2,
                                  nombre_personaje1, nombre_personaje2, vs_cpu, red)
        if resultado != "revancha":
            return
        play_scene_music(escenario_seleccionado)


def show_config():
    selected = 0
    options = ["CONTROLES", "VOLUMEN", "VOLVER"]
    in_config = True
    
    fondo_configuracion = cargar_fondo_configuracion()
    
    fondo_anim_index = 0
    fondo_frame_counter = 0
    fondo_frame_rate = 32  # cambia cada 4 frames
    
    while in_config:
        
        # Actualizar animación de fondo
        fondo_frame_counter += 1
        if fondo_frame_counter >= fondo_frame_rate:
            fondo_anim_index = (fondo_anim_index + 1) % len(fondo_configuracion)
            fondo_frame_counter = 0

        # Dibujar fondo actual
        screen.blit(fondo_configuracion[fondo_anim_index], (0, 0))
        title = FONT.render("CONFIGURACIÓN", True, WHITE)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 120))
        for i, text in enumerate(options):
            color = RED if i == selected else WHITE
            rendered_text = FONT.render(text, True, color)
            screen.blit(rendered_text, (WIDTH // 2 - rendered_text.get_width() // 2, HEIGHT // 2 - 40 + i * 40))
        actualizar_pantalla()
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    in_config = False
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(options)
                elif event.key == pygame.K_RETURN:
                    if options[selected] == "VOLVER":
                        in_config = False
                    elif options[selected] == "CONTROLES":
                        show_controles()
                    elif options[selected] == "VOLUMEN":
                        show_volumen()

def show_controles():
    controles = [
        "COMBATE",
        " ",
        "Jugador 1: A/D = mover, W = saltar, S = cubrirse, E = atacar",
        "Jugador 2: LEFT/RIGHT = mover, UP = saltar, DOWN = cubrirse, NUM 1 (teclado numerico) = atacar",
        " ",
        "SELECCION PERSONAJES",
        " ",
        "Jugador 1: ENTER = Seleccionar, E = Cancelar",
        "Jugador 2: ENTER NUMERICO = Seleccionar, NUM 1 (teclado numerico) = Cancelar",
        "ESPACIO = Confirmar, ESC = Volver",
        " ",
        "SELECCION ESCENARIOS",
        " ",
        "ENTER = Comenzar",
        " ",
        "EN COMBATE: ESC = Pausa      EN CUALQUIER PANTALLA: F11 = Pantalla completa",
        "VS CPU: la CPU controla al Jugador 2 (elige su personaje con las flechas)",
        " ",
        "EN LINEA: mover A/D o flechas, saltar W, atacar E o ESPACIO, cubrir S. ESC dos veces = abandonar",
        "ESTAMINA (barra azul fina bajo la vida): atacar y cubrirse la gastan",
    ]
    waiting = True
    
    fondo_configuracion = cargar_fondo_configuracion()
    
    fondo_anim_index = 0
    fondo_frame_counter = 0
    fondo_frame_rate = 32  # cambia cada 4 frames
    
    while waiting:
        # Actualizar animación de fondo
        fondo_frame_counter += 1
        if fondo_frame_counter >= fondo_frame_rate:
            fondo_anim_index = (fondo_anim_index + 1) % len(fondo_configuracion)
            fondo_frame_counter = 0

        # Dibujar fondo actual
        screen.blit(fondo_configuracion[fondo_anim_index], (0, 0))
        title = FONT2.render("CONTROLES", True, WHITE)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 50))
        for i, linea in enumerate(controles):
            rendered = FONT.render(linea, True, WHITE)
            screen.blit(rendered, (WIDTH // 2 - rendered.get_width() // 2, 180 + i * 40))
        instruction = FONT.render("Presiona ESC para volver", True, RED)
        screen.blit(instruction, (WIDTH // 2 - instruction.get_width() // 2, HEIGHT - 100))
        actualizar_pantalla()
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                waiting = False

def show_volumen():
    sound_volume = punch_sound.get_volume()
    music_volume = pygame.mixer.music.get_volume()
    selected = 0  # 0 para sonido, 1 para música
    running = True
    
    fondo_configuracion = cargar_fondo_configuracion()
    
    fondo_anim_index = 0
    fondo_frame_counter = 0
    fondo_frame_rate = 32  # cambia cada 4 frames
    
    while running:
        # Actualizar animación de fondo
        fondo_frame_counter += 1
        if fondo_frame_counter >= fondo_frame_rate:
            fondo_anim_index = (fondo_anim_index + 1) % len(fondo_configuracion)
            fondo_frame_counter = 0

        # Dibujar fondo actual
        screen.blit(fondo_configuracion[fondo_anim_index], (0, 0))
        title = FONT.render("AJUSTES DE VOLUMEN", True, WHITE)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))
        
        # Volumen de efectos de sonido
        color_sonido = RED if selected == 0 else WHITE
        sonido_text = FONT.render(f"Efectos de sonido: {round(sound_volume*100)}%", True, color_sonido)
        screen.blit(sonido_text, (WIDTH//2 - sonido_text.get_width()//2, HEIGHT//2 - 40))
        
        # Volumen de música
        color_musica = RED if selected == 1 else WHITE
        musica_text = FONT.render(f"Música: {round(music_volume*100)}%", True, color_musica)
        screen.blit(musica_text, (WIDTH//2 - musica_text.get_width()//2, HEIGHT//2 + 20))
        
        instrucciones = FONT.render("↑/↓ para cambiar - ←/→ para ajustar - ESC para salir", True, RED)
        screen.blit(instrucciones, (WIDTH//2 - instrucciones.get_width()//2, HEIGHT - 100))
        
        actualizar_pantalla()
        
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % 2
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % 2
                elif event.key == pygame.K_LEFT:
                    if selected == 0:
                        sound_volume = round(max(0.0, sound_volume - 0.1), 1)
                        punch_sound.set_volume(sound_volume)
                    else:
                        music_volume = round(max(0.0, music_volume - 0.1), 1)
                        pygame.mixer.music.set_volume(music_volume)
                elif event.key == pygame.K_RIGHT:
                    if selected == 0:
                        sound_volume = round(min(1.0, sound_volume + 0.1), 1)
                        punch_sound.set_volume(sound_volume)
                    else:
                        music_volume = round(min(1.0, music_volume + 0.1), 1)
                        pygame.mixer.music.set_volume(music_volume)

def show_winner(winner_name, winner_obj, fondo, red=None):
    """Devuelve 'menu' o 'revancha'. Online, la revancha necesita que los dos pulsen R."""
    # Si no hay sprites de victoria, salimos ANTES de cambiar la música
    if not winner_obj.victoria_sprites:
        print(f"Error: victoria_sprites está vacío para {winner_name}")
        play_menu_music()
        return "menu"

    pygame.mixer.music.stop()
    pygame.mixer.music.load(victoria_sound)
    pygame.mixer.music.play(-1)

    ancho_personaje = winner_obj.rect.width
    alto_personaje = winner_obj.rect.height
    anim_index = 0
    frame_counter = 0
    frame_rate = 10  
    quiero = False
    rival_quiere = False

    resultado = None
    while resultado is None:
        screen.blit(fondo, (0, 0))

        frame_counter += 1
        if frame_counter >= frame_rate and len(winner_obj.victoria_sprites) > 0:
            anim_index = (anim_index + 1) % len(winner_obj.victoria_sprites)
            frame_counter = 0

        sprite = winner_obj.victoria_sprites[anim_index]  # Usar imagen ya cargada
        sprite_escalado = pygame.transform.scale(sprite, (ancho_personaje, alto_personaje + 20))

        if winner_obj.direccion == -1:
            sprite_escalado = pygame.transform.flip(sprite_escalado, True, False)

        x = winner_obj.rect.x
        y = winner_obj.rect.bottom - sprite_escalado.get_height()
        screen.blit(sprite_escalado, (x, y))

        win_text = FONT.render(f"{winner_name} gana!", True, WHITE)
        instruction = FONT.render("Presiona ENTER para volver al menú", True, WHITE)
        if red and quiero:
            txt2 = "Esperando al rival para la revancha..."
        elif red and rival_quiere:
            txt2 = "El rival quiere la revancha: presiona R"
        elif red:
            txt2 = "Presiona R para la revancha (deben querer los dos)"
        else:
            txt2 = "Presiona R para la revancha"
        instruction2 = (FONT_RED if red else FONT).render(txt2, True, WHITE)
        screen.blit(win_text, (WIDTH // 2 - win_text.get_width() // 2, HEIGHT // 2 - 50))
        screen.blit(instruction, (WIDTH // 2 - instruction.get_width() // 2, HEIGHT // 2))
        screen.blit(instruction2, (WIDTH // 2 - instruction2.get_width() // 2, HEIGHT // 2 + 40))

        actualizar_pantalla()
        pygame.time.delay(30)

        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    resultado = "menu"
                    if red:
                        red.enviar({"t": "bye"})
                elif event.key == pygame.K_r:
                    if red:
                        quiero = True
                        red.enviar({"t": "rev"})
                    else:
                        resultado = "revancha"

        if red and resultado is None:
            for m in red.recibir():
                if m.get("t") == "rev":
                    rival_quiere = True
                elif m.get("t") == "bye":
                    resultado = "menu"
            if not red.conectado:
                resultado = "menu"
            elif quiero and rival_quiere:
                resultado = "revancha"

    if resultado == "menu":
        play_menu_music()
    return resultado


def seleccion_personaje():
    nombres_personajes = list(personajes_data.keys())
    # Precargar todos los sprites en memoria
    for nombre in nombres_personajes:
        data = personajes_data[nombre]

        if "victoria_sprites" in data:
            data["victoria_surfaces"] = [
                pygame.transform.scale(
                    pygame.image.load(ruta).convert_alpha(),
                    (player_width, player_height)
                ) for ruta in data["victoria_sprites"]
            ]

        if "parado_sprites" in data:
            data["parado_surfaces"] = [
                pygame.transform.scale(
                    pygame.image.load(ruta).convert_alpha(),
                    (player_width, player_height)
                ) for ruta in data["parado_sprites"]
            ]

    seleccion_p1 = -1
    seleccion_p2 = -1
    selected_index_p1 = 0
    selected_index_p2 = 1
    anim_index_p1 = 0
    frame_counter_p1 = 0
    anim_index_p2 = 0
    frame_counter_p2 = 0
    
    
    
    # Animación victoria índices y contadores
    anim_index_victoria_p1 = 0
    frame_counter_victoria_p1 = 0
    anim_index_victoria_p2 = 0
    frame_counter_victoria_p2 = 0

    start_enabled = False
    big_font = pygame.font.SysFont('Arial', 32)

    cuadro_posiciones_p1 = [
        (-10, -538),   # Penitente (Jugador 1)
        (470, -532),   # Castle Crasher
        (-10, -2),  # Hollow Knight
        (465, -7)   # Shovel Knight
    ]

    cuadro_posiciones_p2 = [
        (0, -5),   # Penitente (Jugador 2)
        (480, 0),   # Castle Crasher
        (0, 530),  # Hollow Knight
        (475, 525)   # Shovel Knight
    ]

    def mover_cursor(index, direccion):
        fila = index // 2
        col = index % 2
        if direccion == "arriba":
            fila = (fila - 1) % 2
        elif direccion == "abajo":
            fila = (fila + 1) % 2
        elif direccion == "izquierda":
            col = (col - 1) % 2
        elif direccion == "derecha":
            col = (col + 1) % 2
        return fila * 2 + col

    # Cargar animación de fondo (fuera del while)
    fondo_animacion = [
    pygame.transform.scale(
        pygame.image.load(f"Seleccion/fondo{i+1}.png").convert_alpha(), (WIDTH, HEIGHT)
    )
    for i in range(28)
    ]
    
    

    fondo_anim_index = 0
    fondo_frame_counter = 0
    fondo_frame_rate = 4  # cambia cada 4 frames

    while True:
        # Actualizar animación de fondo
        fondo_frame_counter += 1
        if fondo_frame_counter >= fondo_frame_rate:
            fondo_anim_index = (fondo_anim_index + 1) % len(fondo_animacion)
            fondo_frame_counter = 0

        # Dibujar fondo actual
        screen.blit(fondo_animacion[fondo_anim_index], (0, 0))

        screen.blit(fondo_personajes, (0, 0))

        # Dibujar cuadros selección
        for i in range(len(nombres_personajes)):
            if i == seleccion_p1 or (i == selected_index_p1 and seleccion_p1 == -1):
                x, y = cuadro_posiciones_p1[i]
                screen.blit(cuadro_rojo, (x, y))
            if i == seleccion_p2 or (i == selected_index_p2 and seleccion_p2 == -1):
                x, y = cuadro_posiciones_p2[i]
                screen.blit(cuadro_azul, (x, y))
                
            # Mostrar texto de inicio
        if seleccion_p1 != -1 and seleccion_p2 != -1:
            start_enabled = True
            start_text = big_font.render(" ", True, BLACK)
        else:
            start_enabled = False
            start_text = big_font.render(" ", True, (150, 150, 150))
        screen.blit(start_text, (WIDTH // 2 - start_text.get_width() // 2, HEIGHT - 100))

                # --- Animación Jugador 1 ---
        if seleccion_p1 != -1:
            nombre = nombres_personajes[seleccion_p1]
            data = personajes_data[nombre]
            pos_x, pos_y = cuadro_posiciones_p1[seleccion_p1]
            pos_y += HEIGHT // 2  # Ajustar al centro verticalmente
            surfaces = data.get("victoria_surfaces", [])
            frame_rate = data.get("animacion_frame_rate_victoria", 8)
            if surfaces:
                frame_counter_victoria_p1 += 1
                if frame_counter_victoria_p1 >= frame_rate:
                    anim_index_victoria_p1 = (anim_index_victoria_p1 + 1) % len(surfaces)
                    frame_counter_victoria_p1 = 0
                try:
                    sprite = surfaces[anim_index_victoria_p1]
                    screen.blit(sprite, (100, HEIGHT - player_height - 50))
                except Exception:
                    pass
            else:
                # Fallback parado
                surfaces = data.get("parado_surfaces", [])
                frame_rate = data.get("animacion_frame_rate_parado", 3)
                if surfaces:
                    frame_counter_p1 += 1
                    if frame_counter_p1 >= frame_rate:
                        anim_index_p1 = (anim_index_p1 + 1) % len(surfaces)
                        frame_counter_p1 = 0
                    try:
                        sprite = surfaces[anim_index_p1]
                        screen.blit(sprite, (100, HEIGHT - player_height - 50))
                    except Exception:
                        pass
        else:
            personaje_index = selected_index_p1
            nombre = nombres_personajes[personaje_index]
            data = personajes_data[nombre]
            pos_x, pos_y = cuadro_posiciones_p1[personaje_index]
            pos_y += HEIGHT // 2
            surfaces = data.get("parado_surfaces", [])
            frame_rate = data.get("animacion_frame_rate_parado", 10)
            if surfaces:
                frame_counter_p1 += 1
                if frame_counter_p1 >= frame_rate:
                    anim_index_p1 = (anim_index_p1 + 1) % len(surfaces)
                    frame_counter_p1 = 0
                try:
                    sprite = surfaces[anim_index_p1]
                    screen.blit(sprite, (100, HEIGHT - player_height - 50))
                except Exception:
                    pass

        # --- Animación Jugador 2 ---
        if seleccion_p2 != -1:
            nombre = nombres_personajes[seleccion_p2]
            data = personajes_data[nombre]
            pos_x, pos_y = cuadro_posiciones_p2[seleccion_p2]
            pos_y += HEIGHT // 2
            surfaces = data.get("victoria_surfaces", [])
            frame_rate = data.get("animacion_frame_rate_victoria", 8)
            if surfaces:
                frame_counter_victoria_p2 += 1
                if frame_counter_victoria_p2 >= frame_rate:
                    anim_index_victoria_p2 = (anim_index_victoria_p2 + 1) % len(surfaces)
                    frame_counter_victoria_p2 = 0
                try:
                    sprite = pygame.transform.flip(surfaces[anim_index_victoria_p2], True, False)
                    screen.blit(sprite, (WIDTH - 100 - player_width, HEIGHT - player_height - 50))
                except Exception:
                    pass
            else:
                # Fallback parado
                surfaces = data.get("parado_surfaces", [])
                frame_rate = data.get("animacion_frame_rate_parado", 3)
                if surfaces:
                    frame_counter_p2 += 1
                    if frame_counter_p2 >= frame_rate:
                        anim_index_p2 = (anim_index_p2 + 1) % len(surfaces)
                        frame_counter_p2 = 0
                    try:
                        sprite = pygame.transform.flip(surfaces[anim_index_p2], True, False)
                        screen.blit(sprite, (WIDTH - 100 - player_width, HEIGHT - player_height - 50))
                    except Exception:
                        pass
        else:
            personaje_index = selected_index_p2
            nombre = nombres_personajes[personaje_index]
            data = personajes_data[nombre]
            pos_x, pos_y = cuadro_posiciones_p2[personaje_index]
            pos_y += HEIGHT // 2
            surfaces = data.get("parado_surfaces", [])
            frame_rate = data.get("animacion_frame_rate_parado", 10)
            if surfaces:
                frame_counter_p2 += 1
                if frame_counter_p2 >= frame_rate:
                    anim_index_p2 = (anim_index_p2 + 1) % len(surfaces)
                    frame_counter_p2 = 0
                try:
                    sprite = pygame.transform.flip(surfaces[anim_index_p2], True, False)
                    screen.blit(sprite, (WIDTH - 100 - player_width, HEIGHT - player_height - 50))
                except Exception:
                    pass


        actualizar_pantalla()

        # Manejo de eventos (igual que antes)
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                # Volver al menú (según lo que dice la pantalla de controles)
                if event.key == pygame.K_ESCAPE:
                    return None

                # Jugador 1
                elif event.key == pygame.K_w:
                    selected_index_p1 = mover_cursor(selected_index_p1, "arriba")
                elif event.key == pygame.K_s:
                    selected_index_p1 = mover_cursor(selected_index_p1, "abajo")
                elif event.key == pygame.K_a:
                    selected_index_p1 = mover_cursor(selected_index_p1, "izquierda")
                elif event.key == pygame.K_d:
                    selected_index_p1 = mover_cursor(selected_index_p1, "derecha")

                # Jugador 2
                elif event.key == pygame.K_UP:
                    selected_index_p2 = mover_cursor(selected_index_p2, "arriba")
                elif event.key == pygame.K_DOWN:
                    selected_index_p2 = mover_cursor(selected_index_p2, "abajo")
                elif event.key == pygame.K_LEFT:
                    selected_index_p2 = mover_cursor(selected_index_p2, "izquierda")
                elif event.key == pygame.K_RIGHT:
                    selected_index_p2 = mover_cursor(selected_index_p2, "derecha")

                elif event.key == pygame.K_RETURN and seleccion_p1 == -1:
                    if selected_index_p1 != seleccion_p2:
                        seleccion_p1 = selected_index_p1
                elif event.key == pygame.K_KP_ENTER and seleccion_p2 == -1:
                    if selected_index_p2 != seleccion_p1:
                        seleccion_p2 = selected_index_p2
                elif event.key == pygame.K_e and seleccion_p1 != -1:
                    seleccion_p1 = -1
                elif event.key == pygame.K_KP1 and seleccion_p2 != -1:
                    seleccion_p2 = -1
                elif event.key == pygame.K_SPACE and start_enabled:
                    return nombres_personajes[seleccion_p1], nombres_personajes[seleccion_p2]




def seleccionar_escenario():
    escenarios = ["Fuerte de Pridemoor", "Coliseo de los Insensatos", "Mundo de lava", "Tumba de la misericordia"]
    seleccionado = 0
    en_seleccion = True

    while en_seleccion:
        escenario_actual = escenarios[seleccionado]
        fondo = fondos_escenarios.get(escenario_actual, None)

        if fondo:
            # Los fondos ya están escalados al tamaño actual de la ventana (no se reescalan en cada frame)
            screen.blit(fondo, (0, 0))
        else:
            screen.fill(BLACK)

        title = FONT.render("SELECCIÓN DE ESCENARIO", True, WHITE)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))

        for i, nombre in enumerate(escenarios):
            color = RED if i == seleccionado else WHITE
            text = FONT.render(nombre, True, color)
            x = WIDTH // 2 - text.get_width() // 2
            y = HEIGHT // 2 - 80 + i * 50  # Espaciado vertical
            screen.blit(text, (x, y))

        instrucciones = FONT.render("↑ ↓ para elegir - ENTER para seleccionar - ESC para volver", True, RED)
        screen.blit(instrucciones, (WIDTH // 2 - instrucciones.get_width() // 2, HEIGHT - 80))

        actualizar_pantalla()

        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_UP:
                    seleccionado = (seleccionado - 1) % len(escenarios)
                elif event.key == pygame.K_DOWN:
                    seleccionado = (seleccionado + 1) % len(escenarios)
                elif event.key == pygame.K_RETURN:
                    return escenarios[seleccionado]


def cargar_escalados(rutas, tamano):
    return [pygame.transform.scale(pygame.image.load(ruta).convert_alpha(), tamano) for ruta in rutas]


def crear_personaje(nombre, escenario, lado):
    """lado = 1 (jugador 1, izquierda) o 2 (jugador 2, derecha)."""
    data = personajes_data[nombre]
    size = data.get("tamaño_personalizado", (player_width, player_height))

    x = 100 if lado == 1 else WIDTH - 100 - size[0]
    y = niveles_suelo[escenario]

    jugador = Personaje(nombre, x, y, size[0], size[1], data["color"],
                        velocidad=data["velocidad"],
                        salto=data["salto"],
                        gravedad=data["gravedad"],
                        vida=data["vida"],
                        vida_maxima=data["vida_maxima"],
                        ataque=data["ataque"],
                        animacion_frame_rate=data["animacion_frame_rate"],
                        animacion_frame_rate_parado=data["animacion_frame_rate_parado"],
                        animacion_frame_rate_ataque=data["animacion_frame_rate_ataque"],
                        animacion_frame_rate_recibir=data["animacion_frame_rate_recibir"],
                        animacion_frame_rate_salto=data["animacion_frame_rate_salto"],
                        tamaño_personalizado=size, sprite_path=data["sprite"])

    if lado == 2:
        jugador.direccion = -1
        jugador.direccion_anterior = -1
        jugador.direccion_inicial = -1

    jugador.parado_sprites = cargar_escalados(data.get("parado_sprites", []), size)
    jugador.caminar_sprites = cargar_escalados(data.get("caminar_sprites", []), size)
    jugador.ataque_sprites = cargar_escalados(data.get("ataque_sprites", []), size)
    jugador.recibir_sprites = cargar_escalados(data.get("recibir_sprites", []), size)
    jugador.salto_sprites = cargar_escalados(data.get("salto_sprites", []), jugador.rect.size)

    victoria_size = victory_sprite_sizes.get(nombre, size)  # Usa tamaño específico de victoria
    jugador.victoria_sprites = cargar_escalados(data.get("victoria_sprites", []), victoria_size)

    jugador.calcular_duracion_ataque()
    jugador.vida = jugador.vida_maxima
    return jugador


# =====================================================================
#                          MODO EN LÍNEA
# El anfitrión (Jugador 1) simula el combate y envía el estado en cada frame.
# El invitado (Jugador 2) envía sus teclas y dibuja el estado recibido.
# =====================================================================
PUERTO_ONLINE = 5555
VERSION_RED = 1
red_info = {"seq": 0, "golpes": 0}   # contadores del anfitrión (numeración de estados y sonidos de golpe)


class Conexion:
    """Conexión TCP no bloqueante que intercambia mensajes JSON (uno por línea)."""
    def __init__(self, sock):
        self.sock = sock
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        sock.setblocking(False)
        self.entrada = b""
        self.salida = b""
        self.pendientes = []
        self.conectado = True
        self.motivo = ""

    def _caer(self, motivo="Se perdió la conexión", forzar=False):
        # forzar=True: el rival avisó que se iba, ese motivo manda aunque el socket ya se haya cerrado
        if self.conectado or forzar:
            self.motivo = motivo
        self.conectado = False
        try:
            self.sock.close()
        except OSError:
            pass

    def cerrar(self):
        self._vaciar()
        self._caer("Conexión cerrada")

    def _vaciar(self):
        if not self.salida or not self.conectado:
            return
        try:
            n = self.sock.send(self.salida)
            self.salida = self.salida[n:]
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            self._caer()
            return
        if len(self.salida) > 1000000:
            self._caer("La conexión es demasiado lenta")

    def enviar(self, mensaje, descartable=False):
        """descartable=True: si hay datos sin enviar (red saturada) se omite para no acumular retraso."""
        if not self.conectado:
            return
        if descartable and self.salida:
            self._vaciar()
            return
        self.salida += (json.dumps(mensaje, separators=(",", ":")) + "\n").encode("utf-8")
        self._vaciar()

    def devolver(self, mensajes):
        """Deja mensajes sin procesar para la próxima llamada a recibir()."""
        self.pendientes = list(mensajes) + self.pendientes

    def recibir(self):
        mensajes = self.pendientes
        self.pendientes = []
        if self.conectado:
            self._vaciar()
            try:
                while True:
                    datos = self.sock.recv(65536)
                    if not datos:
                        self._caer("El rival se desconectó")
                        break
                    self.entrada += datos
            except (BlockingIOError, InterruptedError):
                pass
            except OSError:
                self._caer()
        while b"\n" in self.entrada:
            linea, self.entrada = self.entrada.split(b"\n", 1)
            if linea:
                try:
                    mensajes.append(json.loads(linea.decode("utf-8")))
                except ValueError:
                    pass
        return mensajes


def ip_local():
    try:
        s_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_udp.connect(("8.8.8.8", 80))
        ip = s_udp.getsockname()[0]
        s_udp.close()
        return ip
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def fondo_online():
    screen.fill((15, 15, 28))


def texto_centrado(texto, y, fuente=None, color=WHITE):
    surf = (fuente or FONT_RED).render(texto, True, color)
    screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))


def mensaje_bloqueante(texto, ms=3500):
    fin = pygame.time.get_ticks() + ms
    while pygame.time.get_ticks() < fin:
        fondo_online()
        texto_centrado(texto, HEIGHT // 2 - 30)
        texto_centrado("Pulsa cualquier tecla para continuar", HEIGHT // 2 + 30, color=(170, 170, 170))
        actualizar_pantalla()
        clock.tick(30)
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                return


def show_online_menu():
    opciones = ["CREAR PARTIDA", "UNIRSE A PARTIDA", "VOLVER"]
    sel = 0
    while True:
        fondo_online()
        titulo = FONT2.render("EN LINEA", True, WHITE)
        screen.blit(titulo, (WIDTH // 2 - titulo.get_width() // 2, HEIGHT // 2 - 260))
        for i, texto in enumerate(opciones):
            texto_centrado(texto, HEIGHT // 2 - 100 + i * 60, color=RED if i == sel else WHITE)
        texto_centrado("Crear: tú eres el Jugador 1 y comparte tu IP.   Unirse: escribe la IP del anfitrión.",
                       HEIGHT - 120, color=(170, 170, 170))
        actualizar_pantalla()
        clock.tick(30)
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_UP:
                    sel = (sel - 1) % len(opciones)
                elif event.key == pygame.K_DOWN:
                    sel = (sel + 1) % len(opciones)
                elif event.key == pygame.K_RETURN:
                    return ("host", "join", None)[sel]


def _leer_ultima_ip():
    try:
        with open("ultima_ip.txt", encoding="utf-8") as f:
            return f.read().strip()[:60]
    except OSError:
        return ""


def _guardar_ultima_ip(texto):
    try:
        with open("ultima_ip.txt", "w", encoding="utf-8") as f:
            f.write(texto)
    except OSError:
        pass


def pedir_ip():
    texto = _leer_ultima_ip()
    while True:
        fondo_online()
        texto_centrado("Escribe la IP del anfitrión (ejemplo: 192.168.1.20 o 192.168.1.20:5555)", HEIGHT // 2 - 130)
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        texto_centrado(texto + cursor, HEIGHT // 2 - 40, color=(255, 230, 90))
        texto_centrado("ENTER = conectar      ESC = volver", HEIGHT // 2 + 60, color=(170, 170, 170))
        actualizar_pantalla()
        clock.tick(30)
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_RETURN:
                    if texto.strip():
                        return texto.strip()
                elif event.key == pygame.K_BACKSPACE:
                    texto = texto[:-1]
                elif event.unicode and (event.unicode.isalnum() or event.unicode in ".:-") and len(texto) < 60:
                    texto += event.unicode


def intercambiar_hola(conexion):
    """Comprueba que los dos juegos hablan el mismo protocolo."""
    conexion.enviar({"t": "hola", "v": VERSION_RED})
    fin = pygame.time.get_ticks() + 6000
    while pygame.time.get_ticks() < fin and conexion.conectado:
        mensajes = conexion.recibir()
        for i, m in enumerate(mensajes):
            if m.get("t") == "hola":
                if m.get("v") == VERSION_RED:
                    conexion.devolver(mensajes[i + 1:])
                    return True
                mensaje_bloqueante("Las versiones del juego no coinciden")
                return False
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
        clock.tick(60)
    return False


def esperar_cliente():
    """Anfitrión: abre el puerto y espera al rival. Devuelve Conexion o None."""
    try:
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind(("", PUERTO_ONLINE))
        servidor.listen(1)
        servidor.setblocking(False)
    except OSError:
        mensaje_bloqueante(f"No se pudo abrir el puerto {PUERTO_ONLINE} (¿ya hay otra partida abierta?)")
        return None
    ip = ip_local()
    conexion = None
    cancelado = False
    while conexion is None and not cancelado:
        fondo_online()
        puntos = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        texto_centrado("ESPERANDO AL RIVAL" + puntos, HEIGHT // 2 - 180)
        texto_centrado(f"Tu IP: {ip}      Puerto: {PUERTO_ONLINE}", HEIGHT // 2 - 90, color=(255, 230, 90))
        texto_centrado("Misma red (WiFi/LAN): el rival escribe esa IP.", HEIGHT // 2 - 20, color=(200, 200, 200))
        texto_centrado("Por internet: abre el puerto en tu router o usa una VPN (Tailscale, ZeroTier, Hamachi).",
                       HEIGHT // 2 + 25, color=(200, 200, 200))
        texto_centrado("ESC = cancelar", HEIGHT // 2 + 110, color=(170, 170, 170))
        actualizar_pantalla()
        clock.tick(30)
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                cancelado = True
        try:
            sock, _ = servidor.accept()
            conexion = Conexion(sock)
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            pass
    servidor.close()
    if conexion is None:
        return None
    if not intercambiar_hola(conexion):
        conexion.cerrar()
        return None
    return conexion


def conectar_a(texto_ip):
    """Invitado: conecta con el anfitrión. Devuelve Conexion o None."""
    host, puerto = texto_ip, PUERTO_ONLINE
    if ":" in texto_ip:
        h, _, p = texto_ip.rpartition(":")
        if p.isdigit():
            host, puerto = h, int(p)
    res = {"sock": None, "error": None, "fin": False, "cancelado": False}

    def trabajo():
        try:
            sk = socket.create_connection((host, puerto), timeout=6)
            if res["cancelado"]:
                sk.close()
            else:
                res["sock"] = sk
        except (OSError, ValueError) as e:
            res["error"] = str(e)
        res["fin"] = True

    threading.Thread(target=trabajo, daemon=True).start()
    while not res["fin"]:
        fondo_online()
        puntos = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        texto_centrado(f"CONECTANDO A {host}:{puerto}" + puntos, HEIGHT // 2 - 30)
        texto_centrado("ESC = cancelar", HEIGHT // 2 + 40, color=(170, 170, 170))
        actualizar_pantalla()
        clock.tick(30)
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                res["cancelado"] = True
                return None
    if res["sock"] is None:
        mensaje_bloqueante("No se pudo conectar. Revisa la IP, el puerto y el firewall del anfitrión.")
        return None
    _guardar_ultima_ip(texto_ip)
    conexion = Conexion(res["sock"])
    if not intercambiar_hola(conexion):
        conexion.cerrar()
        return None
    return conexion


_sprites_seleccion_listos = False


def precargar_sprites_seleccion():
    global _sprites_seleccion_listos
    if _sprites_seleccion_listos:
        return
    for nombre, data in personajes_data.items():
        data["victoria_surfaces"] = [
            pygame.transform.scale(pygame.image.load(ruta).convert_alpha(), (player_width, player_height))
            for ruta in data.get("victoria_sprites", [])]
        data["parado_surfaces"] = [
            pygame.transform.scale(pygame.image.load(ruta).convert_alpha(), (player_width, player_height))
            for ruta in data.get("parado_sprites", [])]
    _sprites_seleccion_listos = True


def seleccion_personaje_online(red, soy_host):
    """Cada jugador elige el suyo. Devuelve (nombre_host, nombre_invitado) o None."""
    precargar_sprites_seleccion()
    nombres = list(personajes_data.keys())
    pos_p1 = [(-10, -538), (470, -532), (-10, -2), (465, -7)]
    pos_p2 = [(0, -5), (480, 0), (0, 530), (475, 525)]

    def mover(index, direccion):
        fila, col = index // 2, index % 2
        if direccion == "arriba":
            fila = (fila - 1) % 2
        elif direccion == "abajo":
            fila = (fila + 1) % 2
        elif direccion == "izquierda":
            col = (col - 1) % 2
        elif direccion == "derecha":
            col = (col + 1) % 2
        return fila * 2 + col

    fondo_anim = [pygame.transform.scale(pygame.image.load(f"Seleccion/fondo{i+1}.png").convert_alpha(), (WIDTH, HEIGHT))
                  for i in range(28)]
    fa_idx, fa_cnt = 0, 0
    mi_idx = 0 if soy_host else 1
    rival_idx = 1 if soy_host else 0
    mi_ok = False
    rival_ok = False
    cnt = [0, 0]
    anim = [0, 0]
    enviar_ya = True
    ultimo_envio = 0
    teclas_mov = {pygame.K_w: "arriba", pygame.K_UP: "arriba", pygame.K_s: "abajo", pygame.K_DOWN: "abajo",
                  pygame.K_a: "izquierda", pygame.K_LEFT: "izquierda", pygame.K_d: "derecha", pygame.K_RIGHT: "derecha"}

    while True:
        ahora = pygame.time.get_ticks()
        if enviar_ya or ahora - ultimo_envio > 500:
            red.enviar({"t": "sel", "i": mi_idx, "ok": mi_ok})
            enviar_ya = False
            ultimo_envio = ahora

        otros = []
        for m in red.recibir():
            t = m.get("t")
            if t == "sel":
                rival_idx = int(m.get("i", 0)) % len(nombres)
                rival_ok = bool(m.get("ok"))
            elif t == "bye":
                red._caer("El rival salió de la partida", True)
            else:
                otros.append(m)
        if not red.conectado:
            mensaje_bloqueante(red.motivo)
            return None

        idx_host = mi_idx if soy_host else rival_idx
        idx_cli = rival_idx if soy_host else mi_idx
        ok_host = mi_ok if soy_host else rival_ok
        ok_cli = rival_ok if soy_host else mi_ok
        if mi_ok and rival_ok:
            red.devolver(otros)
            return nombres[idx_host], nombres[idx_cli]

        # --- dibujo ---
        fa_cnt += 1
        if fa_cnt >= 4:
            fa_idx = (fa_idx + 1) % len(fondo_anim)
            fa_cnt = 0
        screen.blit(fondo_anim[fa_idx], (0, 0))
        screen.blit(fondo_personajes, (0, 0))
        screen.blit(cuadro_rojo, pos_p1[idx_host])
        screen.blit(cuadro_azul, pos_p2[idx_cli])
        for lado, idx, ok in ((0, idx_host, ok_host), (1, idx_cli, ok_cli)):
            data = personajes_data[nombres[idx]]
            surfs = (data.get("victoria_surfaces") if ok else None) or data.get("parado_surfaces", [])
            rate = data.get("animacion_frame_rate_victoria", 8) if ok else data.get("animacion_frame_rate_parado", 10)
            if surfs:
                cnt[lado] += 1
                if cnt[lado] >= rate:
                    cnt[lado] = 0
                    anim[lado] = (anim[lado] + 1) % len(surfs)
                sp = surfs[anim[lado] % len(surfs)]
                if lado == 0:
                    screen.blit(sp, (100, HEIGHT - player_height - 50))
                else:
                    screen.blit(pygame.transform.flip(sp, True, False), (WIDTH - 100 - player_width, HEIGHT - player_height - 50))
        texto_centrado("Eres el JUGADOR 1 (anfitrión)" if soy_host else "Eres el JUGADOR 2 (invitado)", 20)
        if mi_ok and not rival_ok:
            texto_centrado("Esperando al rival...", HEIGHT - 70)
        else:
            texto_centrado("Mover: WASD o flechas   ENTER = confirmar   E = cancelar   ESC = salir", HEIGHT - 70)
        actualizar_pantalla()
        clock.tick(60)

        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    red.enviar({"t": "bye"})
                    red.cerrar()
                    return None
                elif event.key in teclas_mov and not mi_ok:
                    mi_idx = mover(mi_idx, teclas_mov[event.key])
                    enviar_ya = True
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and not mi_ok:
                    if not (rival_ok and rival_idx == mi_idx):  # no se puede repetir personaje
                        mi_ok = True
                        enviar_ya = True
                elif event.key in (pygame.K_e, pygame.K_KP1, pygame.K_BACKSPACE) and mi_ok:
                    mi_ok = False
                    enviar_ya = True


def esperar_inicio(red):
    """Invitado: espera a que el anfitrión elija escenario. Devuelve el mensaje 'inicio' o None."""
    while True:
        fondo_online()
        texto_centrado("El anfitrión está eligiendo el escenario...", HEIGHT // 2 - 20)
        texto_centrado("ESC = salir", HEIGHT // 2 + 40, color=(170, 170, 170))
        actualizar_pantalla()
        clock.tick(30)
        for m in red.recibir():
            if m.get("t") == "inicio":
                return m
            elif m.get("t") == "bye":
                red._caer("El anfitrión canceló la partida", True)
        if not red.conectado:
            mensaje_bloqueante(red.motivo)
            return None
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                red.enviar({"t": "bye"})
                red.cerrar()
                return None


# ---------- Estado de juego <-> red ----------
def clave_sprite(j):
    """Identifica qué sprite está usando el personaje (para poder enviarlo por red)."""
    for letra, lista in (("c", j.caminar_sprites), ("p", j.parado_sprites), ("a", j.ataque_sprites),
                         ("r", j.recibir_sprites), ("s", j.salto_sprites)):
        for i, sp in enumerate(lista):
            if sp is j.sprite:
                return [letra, i]
    return ["e", 0]


def sprite_desde_clave(j, clave):
    letra, i = clave
    listas = {"c": j.caminar_sprites, "p": j.parado_sprites, "a": j.ataque_sprites,
              "r": j.recibir_sprites, "s": j.salto_sprites}
    lista = listas.get(letra)
    if lista and 0 <= i < len(lista):
        return lista[i]
    return j.sprite_estatico if j.sprite_estatico is not None else j.sprite


def estado_jugador(j):
    return {"x": j.rect.x, "y": j.rect.y, "d": j.direccion, "v": j.vida, "g": round(j.guardia, 1),
            "gr": int(j.guardia_rota), "b": int(j.bloqueo), "a": int(j.attacking), "s": int(j.saltando),
            "r": int(j.recibiendo), "ia": j.animacion_index_ataque, "is": j.animacion_index_salto,
            "ir": j.animacion_index_recibir, "ib": j.animacion_index_bloqueo, "sp": clave_sprite(j)}


def construir_snapshot(j1, j2, tiempo_s, victorias, texto):
    red_info["seq"] += 1
    return {"t": "snap", "n": red_info["seq"], "ts": tiempo_s, "vic": list(victorias), "txt": texto,
            "p": [estado_jugador(j1), estado_jugador(j2)],
            "fx": [{"x": e["x"], "y": e["y"], "t": e["t"], "dur": e["dur"],
                    "color": list(e["color"]), "grande": e["grande"]} for e in efectos_golpe],
            "sh": fx["shake"], "g": red_info["golpes"]}


def aplicar_estado(j, d):
    j.rect.x, j.rect.y = d["x"], d["y"]
    j.pos_x = float(d["x"])
    j.direccion = d["d"]
    j.vida = d["v"]
    j.guardia = d["g"]
    j.guardia_rota = bool(d["gr"])
    j.bloqueo = bool(d["b"])
    j.attacking = bool(d["a"])
    j.saltando = bool(d["s"])
    j.recibiendo = bool(d["r"])
    j.animacion_index_ataque = d["ia"]
    j.animacion_index_salto = d["is"]
    j.animacion_index_recibir = d["ir"]
    j.animacion_index_bloqueo = d["ib"]
    j.sprite = sprite_desde_clave(j, d["sp"])


def _partida_cliente(escenario, j1, j2, n1, n2, red):
    """Bucle del invitado: envía teclas, recibe el estado y lo dibuja. Devuelve 'menu' o 'revancha'."""
    fondo = fondos_escenarios[escenario]
    ultimo = None
    golpes_vistos = 0
    salir_hasta = 0
    ping = None
    proximo_ping = 0
    efectos_golpe.clear()
    fx["hitstop"] = 0
    fx["shake"] = 0
    while True:
        clock.tick(60)
        ahora = pygame.time.get_ticks()
        for event in obtener_eventos():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if ahora < salir_hasta:
                    red.enviar({"t": "bye"})
                    red.cerrar()
                    return "menu"
                salir_hasta = ahora + 2000

        red.enviar({"t": "in", "m": mascara_teclado(pygame.key.get_pressed())}, descartable=True)
        if ahora >= proximo_ping:
            red.enviar({"t": "ping", "c": ahora})
            proximo_ping = ahora + 1000

        ganador = None
        for m in red.recibir():
            t = m.get("t")
            if t == "snap":
                ultimo = m
            elif t == "ganador":
                ganador = int(m.get("idx", 0))
            elif t == "pong":
                ping = max(0, ahora - int(m.get("c", ahora)))
            elif t == "bye":
                red._caer("El anfitrión abandonó la partida", True)
        if not red.conectado:
            mensaje_bloqueante(red.motivo)
            return "menu"

        if ultimo is not None:
            aplicar_estado(j1, ultimo["p"][0])
            aplicar_estado(j2, ultimo["p"][1])
            efectos_golpe[:] = ultimo["fx"]
            fx["shake"] = ultimo["sh"]
            if ultimo["g"] > golpes_vistos:
                punch_sound.play()
            golpes_vistos = ultimo["g"]

        if ganador is not None:
            nombre = n1 if ganador == 0 else n2
            obj = j1 if ganador == 0 else j2
            return show_winner(nombre, obj, fondo, red)

        if ultimo is not None:
            amp = fx["shake"] // 2 + 1 if fx["shake"] > 0 else 0
            sh = (random.randint(-amp, amp), random.randint(-amp, amp)) if amp else (0, 0)
            draw_window(escenario, j1, j2, n1, n2, tiempo_s=ultimo["ts"], victorias=ultimo["vic"],
                        texto_central=ultimo["txt"], shake=sh, ping=ping,
                        aviso="Pulsa ESC otra vez para abandonar la partida" if ahora < salir_hasta else None)
        else:
            fondo_online()
            texto_centrado("Esperando al anfitrión...", HEIGHT // 2 - 20)
            actualizar_pantalla()


def jugar_online_cliente(escenario, n_host, n_cli, red):
    j1 = crear_personaje(n_host, escenario, 1)
    j2 = crear_personaje(n_cli, escenario, 2)
    while True:
        resultado = _partida_cliente(escenario, j1, j2, n_host, n_cli, red)
        if resultado != "revancha":
            return
        play_scene_music(escenario)


def jugar_online():
    modo = show_online_menu()
    if modo is None:
        return
    if modo == "host":
        red = esperar_cliente()
    else:
        ip = pedir_ip()
        if ip is None:
            return
        red = conectar_a(ip)
    if red is None:
        return
    soy_host = (modo == "host")
    try:
        if pygame.mixer.music.get_volume() > 0:
            pygame.mixer.music.load("Sonidos/seleccion.wav")
            pygame.mixer.music.play(-1)
        sel = seleccion_personaje_online(red, soy_host)
        if sel is None:
            return
        n_host, n_cli = sel
        if soy_host:
            esc = seleccionar_escenario()
            if not esc:
                red.enviar({"t": "bye"})
                return
            red.enviar({"t": "inicio", "esc": esc, "p1": n_host, "p2": n_cli})
            pygame.mixer.music.stop()
            j1 = crear_personaje(n_host, esc, 1)
            j2 = crear_personaje(n_cli, esc, 2)
            play_scene_music(esc)
            run_game(esc, j1, j2, n_host, n_cli, vs_cpu=False, red=red)
        else:
            inicio = esperar_inicio(red)
            if inicio is None:
                return
            esc = inicio["esc"]
            if esc not in fondos_escenarios:
                mensaje_bloqueante("El anfitrión eligió un escenario desconocido")
                return
            pygame.mixer.music.stop()
            play_scene_music(esc)
            jugar_online_cliente(esc, inicio["p1"], inicio["p2"], red)
    finally:
        red.cerrar()
        play_menu_music()


def main():

    show_inicio()

    while True:
        opcion = show_menu()

        if opcion == "ONLINE":
            jugar_online()
        elif opcion in ("JUGAR", "CPU"):
            if pygame.mixer.music.get_volume() > 0:
                pygame.mixer.music.load("Sonidos/seleccion.wav") 
                pygame.mixer.music.play(-1)

            seleccion = seleccion_personaje()
            if seleccion is None:  # ESC en la selección de personajes
                play_menu_music()
                continue
            nombre_personaje1, nombre_personaje2 = seleccion

            escenario_seleccionado = seleccionar_escenario()

            if escenario_seleccionado:
                pygame.mixer.music.stop()
                jugador1 = crear_personaje(nombre_personaje1, escenario_seleccionado, 1)
                jugador2 = crear_personaje(nombre_personaje2, escenario_seleccionado, 2)
                play_scene_music(escenario_seleccionado)
                run_game(escenario_seleccionado, jugador1, jugador2, nombre_personaje1, nombre_personaje2,
                         vs_cpu=(opcion == "CPU"))
            else:
                # ESC en la selección de escenario: volver al menú CON música
                play_menu_music()


if __name__ == "__main__":
    main()