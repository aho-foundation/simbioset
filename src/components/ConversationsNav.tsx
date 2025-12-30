import { createEffect, createSignal, For, onCleanup, onMount, Show } from 'solid-js'
import {
  AmbientLight,
  BufferGeometry,
  Color,
  DirectionalLight,
  Fog,
  Group,
  Line,
  LineBasicMaterial,
  Mesh,
  MeshBasicMaterial,
  MeshPhongMaterial,
  PCFSoftShadowMap,
  PerspectiveCamera,
  PointLight,
  Raycaster,
  Scene,
  SphereGeometry,
  TorusGeometry,
  Vector2,
  Vector3,
  WebGLRenderer
} from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import { useKnowledgeBase } from '../contexts/KnowledgeBaseContext'
import type { ConceptNode } from '../types/kb'
import { getNodeColorHex } from '../utils/colors'
import styles from './ConversationsNav.module.css'

interface ConversationsNavProps {
  nodes: ConceptNode[]
  onNodeSelect?: (node: ConceptNode) => void
}

// Цветовая схема по типам узлов
const NODE_COLORS = {
  question: 0x3b82f6, // Синий
  answer: 0x10b981, // Зелёный
  fact: 0x8b5cf6, // Фиолетовый
  opinion: 0xf59e0b, // Оранжевый
  solution: 0x06b6d4, // Циан
  message: 0x6b7280, // Серый
  default: 0x9ca3af // Светло-серый
}

const ConversationsNav = (props: ConversationsNavProps) => {
  const kb = useKnowledgeBase()

  // Сигнал для режима отображения
  const [is3D, setIs3D] = createSignal(true)

  let containerRef: HTMLDivElement | undefined
  let animationFrameId: number
  let scene: Scene
  let camera: PerspectiveCamera
  let renderer: WebGLRenderer
  let controls: OrbitControls
  let raycaster: Raycaster
  let mouse: Vector2

  // Сигнал для отслеживания ID выбранного узла
  const [nodeMeshes, setNodeMeshes] = createSignal<Map<Mesh, ConceptNode>>(new Map())
  const [selectedNode, setSelectedNode] = createSignal<string | null>(null)
  // Сигнал для хранения данных выбранного узла
  const [selectedNodeData, setSelectedNodeData] = createSignal<ConceptNode | null>(null)
  // Сигнал для отслеживания состояния загрузки
  const [loading, setLoading] = createSignal(false)

  // Функция получения цвета узла
  function getNodeColor(node: ConceptNode): number {
    return NODE_COLORS[node.type as keyof typeof NODE_COLORS] || NODE_COLORS.default
  }

  // Создание узла с улучшенной графикой
  function createNodeMesh(node: ConceptNode, isSelected = false): Group {
    const group = new Group()

    // Основная сфера
    const geometry = new SphereGeometry(0.6, 32, 32)
    const color = getNodeColor(node)
    const material = new MeshPhongMaterial({
      color: color,
      emissive: color,
      emissiveIntensity: isSelected ? 0.6 : 0.2,
      shininess: 100,
      transparent: true,
      opacity: 0.9
    })
    const sphere = new Mesh(geometry, material)
    sphere.castShadow = true
    sphere.receiveShadow = true
    group.add(sphere)

    // Внешнее кольцо (только для выбранного узла)
    if (isSelected) {
      const ringGeometry = new TorusGeometry(0.9, 0.05, 16, 100)
      const ringMaterial = new MeshBasicMaterial({
        color: 0xffd700,
        transparent: true,
        opacity: 0.8
      })
      const ring = new Mesh(ringGeometry, ringMaterial)
      ring.rotation.x = Math.PI / 2
      group.add(ring)
    }

    // Позиция
    group.position.set(node.position.x, node.position.y, node.position.z)

    // Сохраняем ссылку для raycaster
    const meshMap = nodeMeshes()
    meshMap.set(sphere, node)
    setNodeMeshes(meshMap)

    return group
  }

  // Создание связи с градиентом
  function createEdge(from: Vector3, to: Vector3, isHighlighted = false): Line {
    const points = [from, to]
    const geometry = new BufferGeometry().setFromPoints(points)
    const material = new LineBasicMaterial({
      color: isHighlighted ? 0x60a5fa : 0x4b5563,
      opacity: isHighlighted ? 0.8 : 0.4,
      transparent: true,
      linewidth: isHighlighted ? 2 : 1
    })
    const line = new Line(geometry, material)
    return line
  }

  // Генерация позиций для узлов без позиций
  function generateNodePositions(nodes: ConceptNode[]): ConceptNode[] {
    const nodesWithPositions = nodes.map((node, index) => {
      if (node.position && typeof node.position.x === 'number') {
        return node
      }

      // Генерируем позицию по спирали для отсутствующих позиций
      const angle = index * 0.5
      const radius = Math.sqrt(index) * 2
      const x = Math.cos(angle) * radius
      const z = Math.sin(angle) * radius
      const y = (index % 3) * 1.5 // Разные уровни по Y

      return {
        ...node,
        position: { x, y, z }
      }
    })

    return nodesWithPositions
  }

  // Генерация позиций для 2D отображения
  function generateNodePositions2D(nodes: ConceptNode[]): ConceptNode[] {
    const nodesWithPositions = nodes.map((node, index) => {
      if (node.position && typeof node.position.x === 'number') {
        return node
      }

      // Генерируем позицию по кругу для 2D
      const angle = index * 0.5
      const radius = Math.sqrt(index) * 100
      const x = 400 + Math.cos(angle) * radius
      const y = 300 + Math.sin(angle) * radius

      return {
        ...node,
        position: { x, y, z: 0 }
      }
    })

    return nodesWithPositions
  }

  // Расчет связей для 2D
  function calculateEdges(nodes: ConceptNode[]) {
    const nodeMap = new Map(nodes.map((n) => [n.id, n.position]))
    const edges = []

    for (const node of nodes) {
      for (const childId of node.childrenIds) {
        const from = nodeMap.get(node.id)
        const to = nodeMap.get(childId)
        if (from && to) {
          edges.push({ x1: from.x, y1: from.y, x2: to.x, y2: to.y })
        }
      }
    }

    return edges
  }

  // Обработка клика на узел в 2D режиме
  function handleNodeClick(node: ConceptNode) {
    setSelectedNode(node.id)
    setLoading(true)

    kb.getNode(node.id, { includeParent: true, includeChildren: true, includeSiblings: true })
      .then((context) => {
        const allNodes: ConceptNode[] = [context.node]
        if (context.parent) allNodes.push(context.parent)
        allNodes.push(...context.children)
        allNodes.push(...context.siblings)

        if (props.onNodeSelect) {
          props.onNodeSelect(node)
        }
      })
      .catch((error) => console.error('Failed to load node context:', error))
      .finally(() => setLoading(false))
  }

  // Рендеринг 2D графа
  function render2DGraph() {
    const nodes = generateNodePositions2D(props.nodes)
    const edges = calculateEdges(nodes)

    return (
      <svg width="100%" height="100%" viewBox="0 0 800 600" class={styles.svgCanvas}>
        <For each={edges}>
          {(edge) => (
            <line x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} stroke="#4b5563" stroke-width="1" />
          )}
        </For>
        <For each={nodes}>
          {(node) => (
            <circle
              cx={node.position.x}
              cy={node.position.y}
              r="20"
              fill={getNodeColorHex(node.type)}
              stroke={selectedNode() === node.id ? '#ffd700' : 'none'}
              stroke-width={selectedNode() === node.id ? '3' : '0'}
              onClick={() => handleNodeClick(node)}
              style={{ cursor: 'pointer' }}
            />
          )}
        </For>
      </svg>
    )
  }

  // Построение графа
  function buildGraph(nodes: ConceptNode[], selectedId: string | null = null) {
    // Очистка сцены
    while (scene.children.length > 0) {
      const child = scene.children[0]
      if (child instanceof Mesh || child instanceof Line) {
        if (child instanceof Mesh) {
          child.geometry.dispose()
          if (Array.isArray(child.material)) {
            for (const mat of child.material) {
              mat.dispose()
            }
          } else {
            child.material.dispose()
          }
        } else if (child instanceof Line) {
          child.geometry.dispose()
          if (Array.isArray(child.material)) {
            for (const mat of child.material) {
              mat.dispose()
            }
          } else {
            child.material.dispose()
          }
        }
      }
      scene.remove(child)
    }

    setNodeMeshes(new Map())

    // Освещение
    const ambientLight = new AmbientLight(0xffffff, 0.4)
    scene.add(ambientLight)

    const mainLight = new DirectionalLight(0xffffff, 0.8)
    mainLight.position.set(10, 20, 10)
    mainLight.castShadow = true
    mainLight.shadow.mapSize.width = 2048
    mainLight.shadow.mapSize.height = 2048
    scene.add(mainLight)

    const fillLight = new PointLight(0x4a9eff, 0.5)
    fillLight.position.set(-10, 5, -10)
    scene.add(fillLight)

    // Удаление дубликатов узлов и генерация позиций
    const uniqueNodes = Array.from(new Map(nodes.map((node) => [node.id, node])).values())
    const nodesWithPositions = generateNodePositions(uniqueNodes)

    // Создаём узлы
    const nodePositions = new Map<string, Vector3>()
    for (const node of nodesWithPositions) {
      const isSelected = selectedId !== null && node.id === selectedId
      const nodeGroup = createNodeMesh(node, isSelected)
      scene.add(nodeGroup)
      nodePositions.set(node.id, nodeGroup.position)

      if (isSelected) {
        setSelectedNodeData(node)
      }
    }

    // Создаём связи
    for (const node of uniqueNodes) {
      const fromPos = nodePositions.get(node.id)
      if (!fromPos) continue

      for (const childId of node.childrenIds) {
        const toPos = nodePositions.get(childId)
        if (toPos) {
          const isHighlighted = node.id === selectedId || childId === selectedId
          const edge = createEdge(fromPos, toPos, isHighlighted)
          scene.add(edge)
        }
      }
    }
  }

  // Обработка кликов
  function onMouseClick(event: MouseEvent) {
    if (!containerRef) return

    const rect = renderer.domElement.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    raycaster.setFromCamera(mouse, camera)
    const meshArray = Array.from(nodeMeshes().keys())
    const intersects = raycaster.intersectObjects(meshArray)

    if (intersects.length > 0) {
      const clickedMesh = intersects[0].object as Mesh
      const node = nodeMeshes().get(clickedMesh)

      if (node) {
        setSelectedNode(node.id)
        setLoading(true)

        kb.getNode(node.id, { includeParent: true, includeChildren: true, includeSiblings: true })
          .then((context) => {
            const allNodes: ConceptNode[] = [context.node]
            if (context.parent) allNodes.push(context.parent)
            allNodes.push(...context.children)
            allNodes.push(...context.siblings)

            buildGraph(allNodes, node.id)
            if (props.onNodeSelect) {
              props.onNodeSelect(node)
            }
          })
          .catch((error) => console.error('Failed to load node context:', error))
          .finally(() => setLoading(false))
      }
    }
  }

  // Hover эффект
  function onMouseMove(event: MouseEvent) {
    if (!containerRef) return

    const rect = renderer.domElement.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    raycaster.setFromCamera(mouse, camera)
    const meshArray = Array.from(nodeMeshes().keys())
    const intersects = raycaster.intersectObjects(meshArray)

    // Обновление курсора
    renderer.domElement.style.cursor = intersects.length > 0 ? 'pointer' : 'grab'
  }

  // Animation loop
  function animate() {
    animationFrameId = requestAnimationFrame(animate)
    controls.update()
    renderer.render(scene, camera)
  }

  // Инициализация сцены
  onMount(() => {
    if (is3D() && containerRef) {
      // Scene setup с градиентным фоном
      scene = new Scene()
      const fogColor = 0x0a0a1e
      scene.background = new Color(fogColor)
      scene.fog = new Fog(fogColor, 10, 50)

      camera = new PerspectiveCamera(60, containerRef.clientWidth / containerRef.clientHeight, 0.1, 1000)
      camera.position.set(0, 5, 15)

      renderer = new WebGLRenderer({
        antialias: true,
        alpha: true
      })
      renderer.setSize(containerRef.clientWidth, containerRef.clientHeight)
      renderer.setPixelRatio(window.devicePixelRatio)
      renderer.shadowMap.enabled = true
      renderer.shadowMap.type = PCFSoftShadowMap
      containerRef.appendChild(renderer.domElement)

      // Controls с плавностью
      controls = new OrbitControls(camera, renderer.domElement)
      controls.enableDamping = true
      controls.dampingFactor = 0.08
      controls.rotateSpeed = 0.5
      controls.zoomSpeed = 0.8
      controls.minDistance = 5
      controls.maxDistance = 40

      // Raycaster для интерактивности
      raycaster = new Raycaster()
      mouse = new Vector2()

      // Обработчики событий
      renderer.domElement.addEventListener('click', onMouseClick)
      renderer.domElement.addEventListener('mousemove', onMouseMove)

      // Начальное построение с учетом выбранного узла
      buildGraph(props.nodes, selectedNode())

      // Запуск анимации
      animate()

      // Resize handler
      const handleResize = () => {
        if (!containerRef) return
        camera.aspect = containerRef.clientWidth / containerRef.clientHeight
        camera.updateProjectionMatrix()
        renderer.setSize(containerRef.clientWidth, containerRef.clientHeight)
      }
      window.addEventListener('resize', handleResize)

      // Cleanup
      onCleanup(() => {
        window.removeEventListener('resize', handleResize)
        cancelAnimationFrame(animationFrameId)
        renderer.domElement.removeEventListener('click', onMouseClick)
        renderer.domElement.removeEventListener('mousemove', onMouseMove)

        if (containerRef && renderer.domElement.parentNode === containerRef) {
          containerRef.removeChild(renderer.domElement)
        }

        controls.dispose()
        renderer.dispose()
      })
    }
  })

  // Подписка на изменения сигнала selectedNode для обновления отображения
  createEffect(() => {
    if (is3D()) {
      buildGraph(props.nodes, selectedNode())
    }
  })

  return (
    <div class={styles.container}>
      <Show when={is3D()} fallback={<div class={styles.canvas}>{render2DGraph()}</div>}>
        <div ref={containerRef} class={styles.canvas} />
      </Show>

      {/* Панель управления */}
      <div class={styles.controls}>
        <button class={styles.toggleButton} onClick={() => setIs3D(!is3D())}>
          Переключить на {is3D() ? '2D' : '3D'}
        </button>
        <div class={styles.legend}>
          <h3>Типы узлов</h3>
          <div class={styles.legendItem}>
            <span class={styles.colorBox} style={{ background: getNodeColorHex('question') }} />
            <span>Вопрос</span>
          </div>
          <div class={styles.legendItem}>
            <span class={styles.colorBox} style={{ background: getNodeColorHex('answer') }} />
            <span>Ответ</span>
          </div>
          <div class={styles.legendItem}>
            <span class={styles.colorBox} style={{ background: getNodeColorHex('fact') }} />
            <span>Факт</span>
          </div>
          <div class={styles.legendItem}>
            <span class={styles.colorBox} style={{ background: getNodeColorHex('opinion') }} />
            <span>Мнение</span>
          </div>
          <div class={styles.legendItem}>
            <span class={styles.colorBox} style={{ background: getNodeColorHex('solution') }} />
            <span>Решение</span>
          </div>
        </div>
      </div>

      {/* Индикатор загрузки */}
      {loading() && (
        <div class={styles.loader}>
          <div class={styles.spinner} />
          <p>Загрузка контекста...</p>
        </div>
      )}

      {/* Информация о выбранном узле */}
      {selectedNodeData() && (
        <div class={styles.nodeInfo}>
          <div class={styles.nodeInfoHeader}>
            <span class={styles.nodeType}>{selectedNodeData()!.type}</span>
            <button
              class={styles.closeButton}
              onClick={() => {
                setSelectedNode(null)
                setSelectedNodeData(null)
              }}
              title="Закрыть"
            >
              ✕
            </button>
          </div>
          <p class={styles.nodeContent}>
            {selectedNodeData()!.content.substring(0, 200)}
            {selectedNodeData()!.content.length > 200 ? '...' : ''}
          </p>
        </div>
      )}
    </div>
  )
}

export default ConversationsNav
