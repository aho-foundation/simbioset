import { Component } from 'solid-js'
import ClassificationManager from '~/components/ClassificationManager'
import SchemaViewer from '~/components/SchemaViewer'
import styles from './ClassificationPage.module.css'

const ClassificationPage: Component = () => {
  return (
    <div class={styles.container}>
      <div class={styles.header}>
        <h1 class={styles.title}>Управление классификацией и схемой</h1>
        <p class={styles.subtitle}>
          Управляйте тегами классификации и просматривайте схему данных. Автоматическая классификация
          работает в фоне, но вы можете управлять тегами и анализировать их использование.
        </p>
      </div>

      <div class={styles.content}>
        <div class={styles.section}>
          <ClassificationManager />
        </div>

        <div class={styles.section}>
          <SchemaViewer />
        </div>
      </div>
    </div>
  )
}

export default ClassificationPage
