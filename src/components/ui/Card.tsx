import { Component, JSX } from 'solid-js'
import styles from '../../styles/Card.module.css'

type CardProps = {
  children: JSX.Element
  title?: string
  class?: string
}

const Card: Component<CardProps> = (props) => {
  return (
    <div class={`${styles.card} ${props.class || ''}`}>
      {props.title && <h3 class={styles.title}>{props.title}</h3>}
      <div class={styles.content}>{props.children}</div>
    </div>
  )
}

export default Card
