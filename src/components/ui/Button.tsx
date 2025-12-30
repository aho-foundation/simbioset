import { Component, JSX } from 'solid-js'
import styles from '~/styles/Button.module.css'

type ButtonProps = {
  children: JSX.Element
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'outline'
  size?: 'small' | 'medium' | 'large'
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
}

const Button: Component<ButtonProps> = (props) => {
  const variantClass = () => {
    switch (props.variant) {
      case 'secondary':
        return styles.secondary
      case 'outline':
        return styles.outline
      default:
        return styles.primary
    }
  }

  const sizeClass = () => {
    switch (props.size) {
      case 'small':
        return styles.small
      case 'large':
        return styles.large
      default:
        return styles.medium
    }
  }

  return (
    <button
      class={`${styles.button} ${variantClass()} ${sizeClass()}`}
      onClick={props.onClick}
      disabled={props.disabled}
      type={props.type || 'button'}
    >
      {props.children}
    </button>
  )
}

export default Button
