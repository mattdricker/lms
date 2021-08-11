import { LabeledButton } from '@hypothesis/frontend-shared';
import { Fragment, createElement } from 'preact';
import { useContext } from 'preact/hooks';

import { Config } from '../config';

import ErrorDisplay from './ErrorDisplay';
import Dialog from './Dialog';

/**
 * @typedef OAuth2RedirectErrorAppProps
 * @prop {Location} [location] - Test seam
 */

/**
 * Error dialog displayed when authorization with a third-party API via OAuth
 * fails.
 *
 * @param {OAuth2RedirectErrorAppProps} props
 */
export default function OAuth2RedirectErrorApp({ location = window.location }) {
  const {
    OAuth2RedirectError: {
      authUrl = /** @type {string|null} */ (null),
      invalidScope = false,
      errorCode = '',
      errorDetails = '',
      canvasScopes = /** @type {string[]} */ ([]),
    },
  } = useContext(Config);

  const title = () => {
    if (invalidScope) {
      return 'Developer key scopes missing';
    }

    if (errorCode === 'blackboard_missing_integration') {
      return 'Missing blackboard REST API Integration';
    }

    return 'Authorization failed';
  };

  const error = { code: errorCode, details: errorDetails };

  const message = () => {
    if (invalidScope || errorCode !== null) {
      return ' ';
    }
    return 'Something went wrong when authorizing Hypothesis';
  };

  const retry = () => {
    location.href = /** @type {string} */ (authUrl);
  };

  const buttons = [
    <LabeledButton
      key="close"
      onClick={() => window.close()}
      data-testid="close"
    >
      Close
    </LabeledButton>,
  ];

  if (authUrl) {
    buttons.push(
      <LabeledButton
        key="try-again"
        onClick={retry}
        data-testid="try-again"
        variant="primary"
      >
        Try again
      </LabeledButton>
    );
  }

  return (
    <Dialog title={title()} buttons={buttons}>
      {invalidScope && (
        <Fragment>
          <p>
            A Canvas admin needs to edit {"Hypothesis's"} developer key and add
            these scopes:
          </p>
          <ol>
            {canvasScopes.map(scope => (
              <li key={scope}>
                <code>{scope}</code>
              </li>
            ))}
          </ol>
          <p>
            For more information see:{' '}
            <a
              target="_blank"
              rel="noopener noreferrer"
              href="https://github.com/hypothesis/lms/wiki/Canvas-API-Endpoints-Used-by-the-Hypothesis-LMS-App"
            >
              Canvas API Endpoints Used by the Hypothesis LMS App
            </a>
            .
          </p>
        </Fragment>
      )}

      {error.code === 'blackboard_missing_integration' && (
        <Fragment>
          <p>
            A blackboard admin needs to add or enable a REST API integration.
          </p>
          <p>
            For more information see:{' '}
            <a
              target="_blank"
              rel="noopener noreferrer"
              href="https://github.com/hypothesis/lms/wiki/How-to-set-up-Blackboard-API-access-for-the-LMS-app#create-a-rest-api-integration-in-the-blackboard-site"
            >
              Create a REST API Integration in the Blackboard site
            </a>
            .
          </p>
        </Fragment>
      )}
      <ErrorDisplay message={message()} error={error} />
    </Dialog>
  );
}
