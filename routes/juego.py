"""
Juego de Aventura — El Héroe de las Tierras Olvidadas
10 niveles de dificultad creciente integrado en el CRM Tecnocel
"""

from flask import Blueprint, render_template, session, redirect, url_for, request, flash

juego_bp = Blueprint('juego', __name__)

NIVELES = [
    {
        'numero': 1,
        'titulo': 'El Bosque Susurrante',
        'subtitulo': 'Las raíces del peligro',
        'dificultad': 1,
        'icono': 'bi-tree-fill',
        'color': '#00E676',
        'boss': False,
        'historia': (
            'Las ramas te susurran advertencias mientras entras al <strong>Bosque Susurrante</strong>. '
            'Un anciano espíritu emerge de entre los árboles y te ofrece consejo: '
            '"Tres caminos hay, joven aventurero. Elige con sabiduría."'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-compass-fill',
                'texto': 'Seguir el sendero de hongos luminiscentes que marcan el camino ancestral.',
                'resultado': '¡Decisión perfecta! Los hongos te guían con seguridad a través del bosque. Llegas al otro lado descansado y listo para continuar.',
                'puntos': 100,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-scissors',
                'texto': 'Tomar el atajo por la maleza densa, machete en mano.',
                'resultado': 'Te abres paso a través de la maleza. Algunas ramas espinosas te dejan pequeñas heridas, pero llegas al otro lado.',
                'puntos': 50,
                'vida': -15,
            },
            {
                'letra': 'C',
                'icono': 'bi-question-circle-fill',
                'texto': 'Seguir las voces misteriosas que te llaman desde las sombras.',
                'resultado': 'Las voces te llevan en círculos durante horas. Exhausto y con arañazos por todos lados, finalmente encuentras la salida.',
                'puntos': 20,
                'vida': -30,
            },
        ],
    },
    {
        'numero': 2,
        'titulo': 'El Río de las Sombras',
        'subtitulo': 'Aguas traicioneras',
        'dificultad': 2,
        'icono': 'bi-water',
        'color': '#2979FF',
        'boss': False,
        'historia': (
            'Un río oscuro y turbulento bloquea tu camino. Criaturas de sombra se mueven bajo '
            'la superficie del agua mientras observas la otra orilla. '
            'El tiempo apremia y las criaturas parecen cada vez más <strong>agitadas</strong>...'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-sign-turn-right-fill',
                'texto': 'Buscar el antiguo puente de piedra marcado en el mapa ancestral.',
                'resultado': 'El mapa no miente. El viejo puente de piedra aguanta tu peso. Cruzas el río sin contratiempos y con energía renovada.',
                'puntos': 150,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-tools',
                'texto': 'Construir una balsa con los troncos caídos a la orilla.',
                'resultado': 'La balsa aguanta, pero una criatura de sombra te araña el brazo al cruzar. Llegas al otro lado con una herida superficial.',
                'puntos': 75,
                'vida': -20,
            },
            {
                'letra': 'C',
                'icono': 'bi-person-arms-up',
                'texto': 'Nadar directamente a través del río oscuro a toda velocidad.',
                'resultado': 'Las criaturas bajo el agua te atacan repetidamente. Logras cruzar a duras penas, pero estás severamente herido.',
                'puntos': 20,
                'vida': -45,
            },
        ],
    },
    {
        'numero': 3,
        'titulo': 'La Caverna del Eco',
        'subtitulo': 'Oscuridad profunda',
        'dificultad': 3,
        'icono': 'bi-moon-stars-fill',
        'color': '#B388FF',
        'boss': False,
        'historia': (
            'Una caverna profunda y oscura bloquea el paso hacia las montañas. '
            'Los ecos resuenan de manera <strong>sobrenatural</strong> mientras murciélagos gigantes '
            'patrullan el techo rocoso. La oscuridad es total salvo por tu pequeña antorcha...'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-wind',
                'texto': 'Usar la antorcha y seguir la corriente de aire fresco hacia la salida.',
                'resultado': 'El aire fresco te guía perfectamente a través de la caverna. Los murciélagos te ignoran y llegas al otro lado completamente ileso.',
                'puntos': 200,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-ear-fill',
                'texto': 'Navegar por el sonido, tocando las paredes con el bastón.',
                'resultado': 'El método funciona, pero tropiezas con una piedra y te golpeas. Un murciélago también te roza el hombro.',
                'puntos': 100,
                'vida': -25,
            },
            {
                'letra': 'C',
                'icono': 'bi-lightning-fill',
                'texto': 'Correr a través de la caverna en la oscuridad total.',
                'resultado': 'Correr a ciegas fue un error gravísimo. Te golpeas contra múltiples paredes y caes varias veces. Llegas al otro lado magullado.',
                'puntos': 30,
                'vida': -50,
            },
        ],
    },
    {
        'numero': 4,
        'titulo': 'El Desierto Ardiente',
        'subtitulo': 'Calor que abrasa el alma',
        'dificultad': 4,
        'icono': 'bi-sun-fill',
        'color': '#FF6D00',
        'boss': False,
        'historia': (
            'Un desierto de arena ardiente se extiende ante ti. El sol implacable calienta '
            'la arena hasta temperaturas <strong>letales</strong>. A lo lejos, ves espejismos de agua '
            'mientras el calor te sofoca. Cada paso es un suplicio y el horizonte parece infinito...'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-moon-fill',
                'texto': 'Viajar de noche y descansar bajo formaciones rocosas durante el día.',
                'resultado': 'Estrategia perfecta. El fresco de la noche te permite avanzar sin esfuerzo. Cruzas el desierto en perfectas condiciones y bien descansado.',
                'puntos': 250,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-droplet-fill',
                'texto': 'Cubrirse con tela mojada y avanzar lentamente en las horas más frescas.',
                'resultado': 'La tela mojada ayuda, pero el calor es intenso. Llegas deshidratado y agotado al otro lado del desierto.',
                'puntos': 125,
                'vida': -30,
            },
            {
                'letra': 'C',
                'icono': 'bi-speedometer2',
                'texto': 'Correr rápidamente bajo el sol para acortar el tiempo de exposición.',
                'resultado': 'Terrible decisión. El calor extremo te agota en minutos. Llegas al límite de tus fuerzas, quemado y deshidratado.',
                'puntos': 40,
                'vida': -55,
            },
        ],
    },
    {
        'numero': 5,
        'titulo': 'La Torre del Mago',
        'subtitulo': 'ENCUENTRO ESPECIAL — El Mago Valdris',
        'dificultad': 5,
        'icono': 'bi-stars',
        'color': '#FFD740',
        'boss': True,
        'historia': (
            '<span class="badge-especial">⚡ ENCUENTRO ESPECIAL ⚡</span><br><br>'
            'La Torre del Mago bloquea el único paso. El poderoso hechicero <strong>Valdris</strong> '
            'emerge y proclama: "¡Nadie pasa sin superar mi prueba!"<br><br>'
            '<em>El acertijo de Valdris:</em> "Tengo ciudades donde no viven personas, '
            'montañas sin árboles ni piedras, y agua sin peces ni vida. ¿Qué soy?"'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-lightbulb-fill',
                'texto': 'Responder con confianza: "¡Un mapa, sabio Valdris!"',
                'resultado': '¡CORRECTO! Valdris suelta una carcajada: "¡Eres más inteligente de lo que pareces, aventurero!" Te abre paso con respeto y admiración.',
                'puntos': 300,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-file-earmark-text-fill',
                'texto': 'Usar un pergamino mágico del inventario para confundir al mago.',
                'resultado': 'El pergamino crea una distracción, pero Valdris lanza un hechizo antes de que logres escapar. Pasas, pero con quemaduras mágicas.',
                'puntos': 150,
                'vida': -35,
            },
            {
                'letra': 'C',
                'icono': 'bi-shield-fill',
                'texto': 'Intentar atacar al mago físicamente con la espada.',
                'resultado': '¡Atacar a un mago con tu espada! Valdris te lanza por los aires con un chasquido. Te deja pasar, divertido por tu valentía temeraria.',
                'puntos': 50,
                'vida': -60,
            },
        ],
    },
    {
        'numero': 6,
        'titulo': 'El Laberinto de Cristal',
        'subtitulo': 'Ilusiones sin fin',
        'dificultad': 6,
        'icono': 'bi-gem',
        'color': '#00E5FF',
        'boss': False,
        'historia': (
            'Un laberinto de corredores de cristal te rodea completamente. Las paredes '
            'reflejan miles de imágenes tuyas creando <strong>ilusiones imposibles</strong> de distinguir. '
            'Algunas paredes son trampas que explotan al tocarlas. '
            'El laberinto parece respirar y cambiar mientras lo recorres...'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-map-fill',
                'texto': 'Dejar un rastro de monedas y mapear sistemáticamente cada pasillo.',
                'resultado': 'Metódico y brillante. Tu sistema de mapeado te lleva directamente a la salida sin activar ninguna trampa. ¡Perfecto!',
                'puntos': 350,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-eye-fill',
                'texto': 'Seguir el instinto y avanzar probando cada pared antes de tocarla.',
                'resultado': 'Tu instinto es bueno, pero no perfecto. Activas una trampa menor que te deja una herida leve y te hace perder tiempo.',
                'puntos': 175,
                'vida': -35,
            },
            {
                'letra': 'C',
                'icono': 'bi-hammer',
                'texto': 'Destruir las paredes de cristal con el arma para crear el propio camino.',
                'resultado': '¡Las paredes son trampas! Al romperlas liberan energía que te golpea violentamente. Encuentras la salida por accidente, bastante malherido.',
                'puntos': 60,
                'vida': -65,
            },
        ],
    },
    {
        'numero': 7,
        'titulo': 'El Abismo Helado',
        'subtitulo': 'Donde el frío mata',
        'dificultad': 7,
        'icono': 'bi-snow',
        'color': '#82B1FF',
        'boss': False,
        'historia': (
            'Un abismo helado de kilómetros de profundidad se abre ante ti. Puentes de hielo '
            'inestables cruzan el vacío mientras <strong>gigantes de hielo de 5 metros</strong> patrullan '
            'el camino. La temperatura vuelve el acero frágil como vidrio. '
            'Un paso en falso significa caída infinita...'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-journal-text',
                'texto': 'Usar el diario del explorador para encontrar el túnel subterráneo secreto.',
                'resultado': '¡El túnel existe! Es estrecho pero absolutamente sólido. Cruzas el abismo por debajo, lejos de los gigantes de hielo, sin siquiera frío.',
                'puntos': 400,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-trophy-fill',
                'texto': 'Enfrentarse a los gigantes de hielo uno a uno mientras se cruzan los puentes.',
                'resultado': 'Los gigantes son poderosos. Vences a tres de ellos, pero recibes golpes severos que resuenan hasta los huesos. Cruzas con cicatrices nuevas.',
                'puntos': 200,
                'vida': -40,
            },
            {
                'letra': 'C',
                'icono': 'bi-dash-circle-fill',
                'texto': 'Correr cuando los gigantes miran hacia otro lado y esperar no ser detectado.',
                'resultado': 'Los puentes de hielo crujen bajo tus pasos. Uno se rompe y caes, agarrándote por los dedos al borde. Logras subir, pero estás al límite.',
                'puntos': 70,
                'vida': -70,
            },
        ],
    },
    {
        'numero': 8,
        'titulo': 'Las Ruinas Antiguas',
        'subtitulo': 'Secretos de los muertos',
        'dificultad': 8,
        'icono': 'bi-building-fill',
        'color': '#A5D6A7',
        'boss': False,
        'historia': (
            'Ruinas de una civilización perdida, llenas de trampas mortales y <strong>guardianes no-muertos</strong>. '
            'Los muros están cubiertos de runas antiguas que pulsan con energía oscura. '
            'Cada paso podría activar trampas de flechas, pozos de lava, o despertar '
            'a una legión de esqueletos guerreros con miles de años de experiencia en batalla...'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-book-fill',
                'texto': 'Descifrar las runas con el grimorio para desactivar todas las trampas.',
                'resultado': 'Tu conocimiento vale oro. Desactivas cada trampa con elegancia y caminas por las ruinas como si fueran un parque. Los esqueletos no pueden hacer nada.',
                'puntos': 450,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-shield-fill-check',
                'texto': 'Usar el escudo como detector de trampas, golpeando el suelo antes de cada paso.',
                'resultado': 'Metodología sólida pero lenta. Activas algunas trampas de flechas con tu escudo que de todas formas te alcanzan en los brazos.',
                'puntos': 225,
                'vida': -45,
            },
            {
                'letra': 'C',
                'icono': 'bi-arrow-right-circle-fill',
                'texto': 'Cargar hacia adelante confiando en que la armadura resistirá las trampas.',
                'resultado': 'Tu armadura resiste... casi todo. Trampas de lava, flechas envenenadas y esqueletos te golpean repetidamente. Llegas muy malherido.',
                'puntos': 80,
                'vida': -75,
            },
        ],
    },
    {
        'numero': 9,
        'titulo': 'El Volcán de Fuego',
        'subtitulo': 'Las puertas del infierno',
        'dificultad': 9,
        'icono': 'bi-fire',
        'color': '#FF3D00',
        'boss': True,
        'historia': (
            '<span class="badge-especial">🔥 ¡ENCUENTRO ÉPICO! 🔥</span><br><br>'
            'El volcán <strong>Malachar</strong> erupciona constantemente, lanzando ríos de lava por todos lados. '
            'El dragón de fuego <strong>Ignarion</strong> patrulla los cielos y ataca a cualquiera que intente cruzar. '
            'El calor derrite el acero ordinario y la lava fluye entre las pocas '
            'plataformas de roca sólida disponibles. Este es el penúltimo obstáculo...'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-map-fill',
                'texto': 'Usar el mapa de túneles del ermitaño Boros encontrado en las ruinas.',
                'resultado': '¡Los túneles existen y son seguros! Cruzas el volcán por dentro, completamente lejos del dragón y la lava. Llegas al otro lado fresco y victorioso.',
                'puntos': 500,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-droplet-half',
                'texto': 'Usar pociones de resistencia al fuego y navegar entre las plataformas de roca.',
                'resultado': 'Las pociones ayudan enormemente, pero Ignarion te detecta y lanza una llamarada. Esquivas la mayoría, pero algo de lava te alcanza.',
                'puntos': 250,
                'vida': -50,
            },
            {
                'letra': 'C',
                'icono': 'bi-controller',
                'texto': 'Montar un grifo salvaje y atacar directamente al dragón Ignarion en combate aéreo.',
                'resultado': '¡El combate con Ignarion es épico pero brutal! Ganas tras una batalla legendaria, pero tanto tú como el grifo están gravemente heridos.',
                'puntos': 90,
                'vida': -80,
            },
        ],
    },
    {
        'numero': 10,
        'titulo': 'El Castillo Oscuro',
        'subtitulo': 'BATALLA FINAL — El Señor Oscuro Malachar',
        'dificultad': 10,
        'icono': 'bi-shield-fill-exclamation',
        'color': '#B71C1C',
        'boss': True,
        'historia': (
            '<span class="badge-final">💀 ¡EL ENFRENTAMIENTO FINAL! 💀</span><br><br>'
            'Has llegado al <strong>Castillo Oscuro</strong>. El Señor Oscuro <strong>Malachar</strong> flota ante ti, '
            'bañado en energía negra pura, sosteniendo el <em>Cristal de la Eternidad</em> en sus '
            'garras de sombra.<br><br>'
            '"Pequeño insecto", truena su voz, "has llegado lejos, pero aquí termina tu historia."<br><br>'
            '¿Cómo enfrentas al <strong>mal supremo</strong>?'
        ),
        'opciones': [
            {
                'letra': 'A',
                'icono': 'bi-brightness-high-fill',
                'texto': 'Reflejar la energía del Cristal con el escudo para golpear al propio Malachar.',
                'resultado': '¡VICTORIA ÉPICA! La energía del Cristal, reflejada perfectamente, golpea a Malachar en su núcleo. Con un grito que hace temblar el castillo, el Señor Oscuro es destruido para siempre. ¡El Cristal de la Eternidad es tuyo!',
                'puntos': 600,
                'vida': 0,
            },
            {
                'letra': 'B',
                'icono': 'bi-people-fill',
                'texto': 'Convocar a todos los aliados del viaje para un ataque coordinado masivo.',
                'resultado': '¡Victoria compartida! Con el apoyo de todos tus aliados, Malachar es derrotado. Recibes heridas serias, pero la victoria pertenece a todos.',
                'puntos': 300,
                'vida': -50,
            },
            {
                'letra': 'C',
                'icono': 'bi-person-fill',
                'texto': 'Enfrentarte a Malachar en combate singular con toda tu fuerza y voluntad.',
                'resultado': '¡Victoria heroica pero sangrienta! En un duelo de pura voluntad que dura horas, derrotas a Malachar. Estás al borde de la muerte, pero eres el campeón del mundo.',
                'puntos': 100,
                'vida': -90,
            },
        ],
    },
]

PUNTUACION_MAXIMA = sum(
    max(op['puntos'] for op in n['opciones']) for n in NIVELES
)


def get_nivel(numero):
    for n in NIVELES:
        if n['numero'] == numero:
            return n
    return None


@juego_bp.route('/')
def inicio():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    juego = session.get('juego')
    return render_template(
        'juego/inicio.html',
        juego=juego,
        total_niveles=len(NIVELES),
        puntuacion_maxima=PUNTUACION_MAXIMA,
    )


@juego_bp.route('/nuevo', methods=['POST'])
def nuevo():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    nombre = request.form.get('nombre', '').strip() or 'Héroe Anónimo'
    session['juego'] = {
        'nombre': nombre,
        'nivel': 1,
        'vida': 100,
        'puntos': 0,
        'estado': 'jugando',
        'mostrando_resultado': False,
        'ultimo_resultado': None,
    }
    session.modified = True
    return redirect(url_for('juego.jugar'))


@juego_bp.route('/jugar')
def jugar():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    juego = session.get('juego')
    if not juego:
        return redirect(url_for('juego.inicio'))

    estado = juego.get('estado', 'jugando')
    mostrando = juego.get('mostrando_resultado', False)

    if estado in ('muerto', 'ganado') and not mostrando:
        return redirect(url_for('juego.resultado'))

    nivel_data = get_nivel(juego['nivel'])
    if not nivel_data:
        return redirect(url_for('juego.resultado'))

    return render_template(
        'juego/jugar.html',
        juego=juego,
        nivel=nivel_data,
        total_niveles=len(NIVELES),
        mostrando=mostrando,
        ultimo_resultado=juego.get('ultimo_resultado'),
    )


@juego_bp.route('/elegir', methods=['POST'])
def elegir():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    juego = session.get('juego')
    if not juego or juego.get('estado') != 'jugando':
        return redirect(url_for('juego.inicio'))

    letra = request.form.get('opcion', '').upper()
    nivel_data = get_nivel(juego['nivel'])
    if not nivel_data:
        return redirect(url_for('juego.resultado'))

    opcion = next((op for op in nivel_data['opciones'] if op['letra'] == letra), None)
    if not opcion:
        flash('Opción no válida.', 'warning')
        return redirect(url_for('juego.jugar'))

    juego['puntos'] += opcion['puntos']
    juego['vida'] = max(0, juego['vida'] + opcion['vida'])
    juego['mostrando_resultado'] = True
    juego['ultimo_resultado'] = {
        'letra': letra,
        'opcion_texto': opcion['texto'],
        'resultado_texto': opcion['resultado'],
        'puntos_ganados': opcion['puntos'],
        'vida_perdida': abs(opcion['vida']) if opcion['vida'] < 0 else 0,
        'optima': opcion['vida'] == 0,
    }

    if juego['vida'] <= 0:
        juego['estado'] = 'muerto'
    elif juego['nivel'] >= len(NIVELES):
        juego['estado'] = 'ganado'

    session.modified = True
    return redirect(url_for('juego.jugar'))


@juego_bp.route('/continuar', methods=['POST'])
def continuar():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    juego = session.get('juego')
    if not juego:
        return redirect(url_for('juego.inicio'))

    estado = juego.get('estado', 'jugando')
    if estado in ('muerto', 'ganado'):
        juego['mostrando_resultado'] = False
        session.modified = True
        return redirect(url_for('juego.resultado'))

    juego['nivel'] += 1
    juego['mostrando_resultado'] = False
    juego['ultimo_resultado'] = None

    if juego['nivel'] > len(NIVELES):
        juego['estado'] = 'ganado'

    session.modified = True
    return redirect(url_for('juego.jugar'))


@juego_bp.route('/resultado')
def resultado():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    juego = session.get('juego')
    if not juego:
        return redirect(url_for('juego.inicio'))

    niveles_completados = juego['nivel'] - 1 if juego.get('estado') == 'muerto' else juego['nivel']
    if juego.get('estado') == 'ganado':
        niveles_completados = len(NIVELES)

    pct_puntos = round((juego['puntos'] / PUNTUACION_MAXIMA) * 100)

    return render_template(
        'juego/resultado.html',
        juego=juego,
        total_niveles=len(NIVELES),
        niveles_completados=niveles_completados,
        puntuacion_maxima=PUNTUACION_MAXIMA,
        pct_puntos=pct_puntos,
    )


@juego_bp.route('/reiniciar', methods=['POST'])
def reiniciar():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    session.pop('juego', None)
    return redirect(url_for('juego.inicio'))
