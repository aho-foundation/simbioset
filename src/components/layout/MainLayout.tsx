import { JSX } from 'solid-js'
import styles from '~/styles/MainLayout.module.css'
import Header from './Header'

interface MainLayoutProps {
  children?: JSX.Element
}

const MainLayout = (props: MainLayoutProps) => {
  return (
    <div class={styles.layout}>
      <Header />
      <main class={styles.mainContent}>{props.children}</main>
    </div>
  )
}

export default MainLayout
