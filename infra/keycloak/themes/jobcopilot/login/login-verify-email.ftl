<#--
  Override of base/login/login-verify-email.ftl (rendered inside the
  keycloak.v2 template). Change vs stock: the info section gains a
  cross-device hint and a "continue to sign in" action.

  Why: Keycloak completes verification (and, with the 26.7 register-then-set-
  password flow, the password setup) in whichever browser opens the email
  link. When that is a phone, THIS page — still open in the originating
  browser — offered nothing but "re-send email": a dead end. The continue
  link restarts the login flow so the user can sign in with the password
  they just set. Keep the structure in sync with the stock template when
  upgrading Keycloak.
-->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayInfo=true; section>
    <#if section = "header">
        ${msg("emailVerifyTitle")}
    <#elseif section = "form">
        <p class="instruction">
            <#if verifyEmail??>
                ${msg("emailVerifyInstruction1",verifyEmail)}
            <#else>
                ${msg("emailVerifyInstruction4",user.email)}
            </#if>
        </p>
        <#if isAppInitiatedAction??>
            <form id="kc-verify-email-form" class="${properties.kcFormClass!}" action="${url.loginAction}" method="post">
                <div class="${properties.kcFormGroupClass!}">
                    <div id="kc-form-buttons" class="${properties.kcFormButtonsClass!}">
                        <#if verifyEmail??>
                            <input class="${properties.kcButtonClass!} ${properties.kcButtonDefaultClass!} ${properties.kcButtonLargeClass!}" type="submit" value="${msg("emailVerifyResend")}" />
                        <#else>
                            <input class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonLargeClass!}" type="submit" value="${msg("emailVerifySend")}" />
                        </#if>
                        <button class="${properties.kcButtonClass!} ${properties.kcButtonDefaultClass!} ${properties.kcButtonLargeClass!}" type="submit" name="cancel-aia" value="true" formnovalidate>${msg("doCancel")}</button>
                    </div>
                </div>
            </form>
        </#if>
    <#elseif section = "info">
        <#if !isAppInitiatedAction??>
            <p class="instruction">
                ${msg("emailVerifyInstruction2")}
                <br/>
                <a href="${url.loginAction}">${msg("doClickHere")}</a> ${msg("emailVerifyInstruction3")}
            </p>
            <p class="instruction" id="kc-verify-email-cross-device-hint">
                ${msg("emailVerifyCrossDeviceHint")}
            </p>
            <a id="kc-verify-email-continue"
               class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!}"
               href="${url.loginRestartFlowUrl}">${msg("emailVerifyContinue")}</a>
        </#if>
    </#if>
</@layout.registrationLayout>
