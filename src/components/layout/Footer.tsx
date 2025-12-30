import { Component } from 'solid-js'
import { useI18n } from '~/i18n'
import styles from '~/styles/Footer.module.css'

const Footer: Component = () => {
  const { t } = useI18n()

  return (
    <footer class={styles.footer}>
      <div class={styles.container}>
        <div class={styles.copyright}>
          <p>
            &copy; {new Date().getFullYear()} {t('Симбиосеть')} - {t('Планетарный стетоскоп')}
          </p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
