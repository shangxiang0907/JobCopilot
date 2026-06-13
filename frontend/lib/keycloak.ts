import Keycloak from "keycloak-js"

declare global {
  interface Window {
    __ENV__: {
      KEYCLOAK_URL: string
      KEYCLOAK_REALM: string
      KEYCLOAK_CLIENT_ID: string
    }
  }
}

let instance: Keycloak | null = null

export function getKeycloak(): Keycloak {
  if (!instance) {
    const env = window.__ENV__
    instance = new Keycloak({
      url: env.KEYCLOAK_URL,
      realm: env.KEYCLOAK_REALM,
      clientId: env.KEYCLOAK_CLIENT_ID,
    })
  }
  return instance
}
