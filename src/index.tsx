/* @refresh reload */
import 'solid-devtools'

import { Router } from '@solidjs/router'
import { render } from 'solid-js/web'
import App from './app'
import { routes } from './routes'

const root = document.getElementById('root')

if (!(root instanceof HTMLElement)) {
  throw new Error('Root element not found')
}

render(() => <Router root={(props) => <App>{props.children}</App>}>{routes}</Router>, root)
