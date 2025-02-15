import { mount } from 'enzyme';
import { Fragment, createElement } from 'preact';
import { act } from 'preact/test-utils';

import { APIError } from '../../utils/api';
import FileList from '../FileList';
import LMSFilePicker, { $imports } from '../LMSFilePicker';
import mockImportedComponents from '../../../test-util/mock-imported-components';
import { waitFor, waitForElement } from '../../../test-util/wait';

describe('LMSFilePicker', () => {
  // eslint-disable-next-line react/prop-types
  const FakeDialog = ({ buttons, children }) => (
    <Fragment>
      {buttons} {children}
    </Fragment>
  );

  let fakeApiCall;
  let fakeListFilesApi;
  let fakeFiles;
  let fakeFolders;

  const renderFilePicker = (props = {}) => {
    return mount(
      <LMSFilePicker
        authToken="auth-token"
        listFilesApi={fakeListFilesApi}
        onAuthorized={sinon.stub()}
        onSelectFile={sinon.stub()}
        onCancel={sinon.stub()}
        missingFilesHelpLink={'https://fake_help_link'}
        {...props}
      />
    );
  };

  const changePath = (wrapper, folder) => {
    act(() => wrapper.find('Breadcrumbs').props().onSelectItem(folder));
  };

  beforeEach(() => {
    fakeFiles = [
      { type: 'File', display_name: 'A file' },
      { type: 'Folder', display_name: 'A folder' },
    ];

    fakeFolders = [
      {
        display_name: 'Subfolder',
        id: 'subfolder',
        type: 'Folder',
        contents: {
          path: 'folder-path',
        },
      },
      {
        display_name: 'Subfolder2',
        id: 'subfolder2',
        type: 'Folder',
        contents: {
          path: 'folder2-path',
        },
      },
    ];

    fakeListFilesApi = {
      path: 'https://lms.anno.co/files/course123',
      authUrl: 'https://lms.anno.co/authorize-lms',
    };

    fakeApiCall = sinon.stub().resolves(fakeFiles);

    $imports.$mock(mockImportedComponents());
    $imports.$mock({
      '../utils/api': {
        apiCall: fakeApiCall,
      },
      './Dialog': FakeDialog,
      // Don't mock <FileList> because <NoFiles> requires
      // it to render for code coverage.
      './FileList': FileList,
    });
  });

  afterEach(() => {
    $imports.$restore();
  });

  it('fetches files when the dialog first appears', async () => {
    const wrapper = renderFilePicker();

    assert.calledWith(fakeApiCall, {
      authToken: 'auth-token',
      path: fakeListFilesApi.path,
    });

    const expectedFiles = await fakeApiCall.returnValues[0];
    const fileList = await waitForElement(wrapper, 'FileList');
    assert.deepEqual(fileList.prop('files'), expectedFiles);
  });

  it('shows breadcrumbs if `withBreadcrumbs` enabled', async () => {
    const wrapper = renderFilePicker({ withBreadcrumbs: true });

    const breadcrumbs = await waitForElement(wrapper, 'Breadcrumbs');

    const items = breadcrumbs.props().items;
    assert.lengthOf(items, 1);
    assert.include(
      items[0],
      {
        display_name: 'Files',
        id: '__root__',
      },
      'The only initial breadcrumb is the top-level "Files" crumb'
    );

    assert.equal(
      breadcrumbs.props().renderItem(fakeFolders[0]),
      'Subfolder',
      'The `renderItem` callback passed to Breadcrumbs renders a File `display_name`'
    );
  });

  it('fetches files in indicated sub-folder if folder path is changed', async () => {
    const wrapper = renderFilePicker({ withBreadcrumbs: true });

    const breadcrumbs = await waitForElement(wrapper, 'Breadcrumbs');
    fakeApiCall.reset();
    // Simulate changing the folder path, as if a user clicked on a "crumb"
    act(() => breadcrumbs.props().onSelectItem(fakeFolders[0]));

    await waitFor(() => fakeApiCall.calledOnce);

    assert.calledWith(fakeApiCall, {
      authToken: 'auth-token',
      path: fakeFolders[0].contents.path,
    });
  });

  it('updates Breadcrumbs when folder path changes', async () => {
    const wrapper = renderFilePicker({ withBreadcrumbs: true });
    await waitForElement(wrapper, 'Breadcrumbs');

    // Simulate changing the path into subfolder `fakeFolders[0]`
    changePath(wrapper, fakeFolders[0]);
    wrapper.update();

    const breadcrumbs = wrapper.find('Breadcrumbs');
    const pathItems = breadcrumbs.props().items;

    // Now there is the top "Files" item and a single subfolder
    assert.lengthOf(pathItems, 2);
    // The last item is the sub-folder just changed to, `fakeFolders[0]`
    assert.deepEqual(pathItems[1], fakeFolders[0]);

    // Simulate changing the path again into a nested subfolder `fakeFolders[1]`
    changePath(wrapper, fakeFolders[1]);
    wrapper.update();
    const pathItems2 = wrapper.find('Breadcrumbs').props().items;

    // Now there are three breadcrumbs, with `fakeFolders[1]` as the last item
    assert.lengthOf(pathItems2, 3);
    assert.deepEqual(pathItems2[2], fakeFolders[1]);

    // Now head back "up" the hierarchy one level (`fakeFolders[0]`)
    changePath(wrapper, fakeFolders[0]);
    wrapper.update();
    const pathItems3 = wrapper.find('Breadcrumbs').props().items;

    // This removes `fakeFolders[1]` from the path items, and the last item is
    // the folder path just switched to (`fakeFolders[0]`)
    assert.lengthOf(pathItems3, 2);
    assert.deepEqual(pathItems3[1], fakeFolders[0]);
  });

  it('shows the authorization prompt if fetching files fails with an APIError that has no `errorMessage`', async () => {
    fakeApiCall.rejects(
      new APIError('Not authorized', {
        /** without errorMessage */
      })
    );

    // Wait for the initial file fetch to fail.
    const wrapper = renderFilePicker();
    try {
      await fakeApiCall;
    } catch {
      /* unused */
    }
    wrapper.update();
    assert.called(fakeApiCall);

    // Check that the "Authorize" button is shown.
    const authButton = wrapper.find('AuthButton');
    assert.isTrue(authButton.exists());

    // Click the "Authorize" button and check that files are re-fetched.
    const expectedFiles = ['a file'];
    fakeApiCall.reset();
    fakeApiCall.resolves(expectedFiles);

    await act(() => authButton.prop('onAuthComplete')());
    wrapper.update();

    assert.calledWith(fakeApiCall, {
      authToken: 'auth-token',
      path: fakeListFilesApi.path,
    });

    const fileList = wrapper.find('FileList');
    assert.deepEqual(fileList.prop('files'), expectedFiles);
  });

  it('shows the "Authorize" and "Try again" buttons after 2 failed authorization requests', async () => {
    fakeApiCall.rejects(
      new APIError('Not authorized', {
        /** without errorMessage */
      })
    );

    const wrapper = renderFilePicker();
    try {
      await fakeApiCall;
    } catch {
      /* unused */
    }
    wrapper.update();
    assert.called(fakeApiCall);

    // Make initial authorization request, which fails.
    const authButton = wrapper.find('AuthButton');
    assert.isTrue(authButton.exists());
    assert.isTrue(wrapper.exists('p[data-testid="authorization warning"]'));

    // Make unsuccessful authorization attempt and wait for re-fetching files
    // to fail.
    await act(() => authButton.prop('onAuthComplete')());
    wrapper.update();

    // Make second authorization request, which succeeds.
    const tryAgainButton = wrapper.find('AuthButton');
    assert.isTrue(tryAgainButton.exists());
    assert.equal(tryAgainButton.prop('label'), 'Try again');
    const errorDetails = wrapper.find('ErrorDisplay');
    assert.equal(
      errorDetails.prop('message'),
      'Failed to authorize file access'
    );
    assert.equal(errorDetails.prop('error').message, '');

    // Make successful authorization attempt and wait for the auth window to close.
    fakeApiCall.reset();
    fakeApiCall.resolves([0]);
    await fakeApiCall;
    wrapper.update();

    await act(() => tryAgainButton.prop('onAuthComplete')());
    wrapper.update();

    // After authorization completes, files should be fetched and then the
    // file list should be displayed.
    assert.isTrue(wrapper.exists('FileList'));
    assert.isFalse(wrapper.exists('AuthButton'));
    assert.isFalse(wrapper.exists('p[data-testid="authorization warning"]'));
    assert.isFalse(wrapper.exists('ErrorDisplay'));
  });

  [
    {
      description: 'a server error with details',
      error: new APIError('Not authorized', {
        message: 'Some error detail',
      }),
    },
    {
      description: 'a network or other error',
      error: new Error('Failed to fetch'),
    },
  ].forEach(({ description, error }) => {
    it(`shows error details and "Try again" button if fetching files fails with ${description}`, async () => {
      fakeApiCall.rejects(error);

      // When the dialog is initially displayed, it should try to fetch files.
      const wrapper = renderFilePicker();
      try {
        await fakeApiCall;
      } catch {
        /* unused */
      }
      wrapper.update();
      assert.called(fakeApiCall);

      // The details of the error should be displayed, along with a "Try again"
      // button.
      const tryAgainButton = wrapper.find(
        'AuthButton[data-testid="try-again"]'
      );
      assert.isTrue(tryAgainButton.exists());

      const errorDetails = wrapper.find('ErrorDisplay');
      assert.include(errorDetails.props(), {
        message: 'There was a problem fetching files',
        error,
      });

      // Clicking the "Try again" button should re-try authorization.
      fakeApiCall.reset();
      fakeApiCall.resolves([]);

      await act(() => tryAgainButton.prop('onAuthComplete')());
      wrapper.update();

      // After authorization completes, files should be fetched and then the
      // file list should be displayed.
      await fakeApiCall;
      wrapper.update();
      assert.isTrue(wrapper.exists('FileList'), 'File list was not displayed');
    });
  });

  it('shows "Reload" button when the request returns no files', async () => {
    const clock = sinon.useFakeTimers();
    fakeApiCall.onFirstCall().resolves([]);
    // When the dialog is initially displayed, it should try to fetch files.
    const wrapper = renderFilePicker();
    await fakeApiCall;
    wrapper.update();
    assert.called(fakeApiCall);

    const reloadButton = wrapper.find('LabeledButton[data-testid="reload"]');
    assert.isFalse(reloadButton.prop('disabled'));

    const waitMs = 3000;
    fakeApiCall
      .onSecondCall()
      .resolves(new Promise(resolve => setTimeout(() => resolve([]), waitMs)));

    reloadButton.prop('onClick')();
    wrapper.update();

    assert.isTrue(
      wrapper.find('LabeledButton[data-testid="reload"]').prop('disabled')
    );

    clock.tick(waitMs);
    await fakeApiCall;
    wrapper.update();

    assert.isFalse(
      wrapper.find('LabeledButton[data-testid="reload"]').prop('disabled')
    );

    clock.restore();
  });

  it('shows a "Select" button when the request return a list with one or more files', async () => {
    fakeApiCall.resolves([0]);
    // When the dialog is initially displayed, it should try to fetch files.
    const wrapper = renderFilePicker();
    await fakeApiCall;
    wrapper.update();
    assert.called(fakeApiCall);

    assert.isTrue(wrapper.exists('LabeledButton[data-testid="select"]'));
  });

  it('fetches and displays files from the LMS', async () => {
    const wrapper = renderFilePicker();
    const expectedFiles = await fakeApiCall.returnValues[0];
    wrapper.update();
    assert.called(fakeApiCall);

    const fileList = wrapper.find('FileList');
    assert.deepEqual(fileList.prop('files'), expectedFiles);
  });

  it('maintains selected file state', async () => {
    const wrapper = renderFilePicker();
    await fakeApiCall;
    wrapper.update();

    const file = { id: 123 };

    wrapper.find('FileList').prop('onSelectFile')(file);
    wrapper.update();

    assert.equal(wrapper.find('FileList').prop('selectedFile'), file);
  });

  it('invokes `onSelectFile` when user chooses a file', async () => {
    const onSelectFile = sinon.stub();
    const wrapper = renderFilePicker({ onSelectFile });
    await fakeApiCall;
    wrapper.update();

    const file = { id: 123 };
    wrapper.find('FileList').prop('onUseFile')(file);
    assert.calledWith(onSelectFile, file);
  });

  it('does not invoke `onSelectFile` if chosen file is empty', async () => {
    const onSelectFile = sinon.stub();
    const wrapper = renderFilePicker({ onSelectFile });
    await waitFor(() => fakeApiCall.called);
    wrapper.update();

    const file = null;
    wrapper.find('FileList').prop('onUseFile')(file);
    assert.notCalled(onSelectFile);
  });

  it('updates the folder path when a user chooses a folder', async () => {
    const onSelectFile = sinon.stub();
    const wrapper = renderFilePicker({ onSelectFile, withBreadcrumbs: true });
    await waitFor(() => fakeApiCall.called);
    wrapper.update();

    const file = fakeFiles[1]; // This is a folder
    wrapper.find('FileList').prop('onUseFile')(file);
    // Folders cannot be selected as a file...
    assert.notCalled(onSelectFile);

    await waitFor(() => fakeApiCall.calledTwice);
    wrapper.update();

    // ...Instead, the path state is updated (and "navigated to") and added
    // to the set of breadcrumb path elements
    assert.equal(wrapper.find('Breadcrumbs').props().items[1], fakeFiles[1]);
  });

  it('disables "Select" button when no file is selected', async () => {
    const wrapper = renderFilePicker();
    await waitFor(() => fakeApiCall.called);
    wrapper.update();

    assert.equal(
      wrapper.find('LabeledButton[data-testid="select"]').prop('disabled'),
      true
    );
  });

  it('enables "Select" button when a file is selected', async () => {
    const wrapper = renderFilePicker();
    await waitFor(() => fakeApiCall.called);
    wrapper.update();

    wrapper.find('FileList').prop('onSelectFile')({ id: 123 });
    wrapper.update();

    assert.equal(
      wrapper.find('LabeledButton[data-testid="select"]').prop('disabled'),
      false
    );
  });

  it('chooses selected file when uses clicks "Select" button', async () => {
    const onSelectFile = sinon.stub();
    const wrapper = renderFilePicker({ onSelectFile });
    await waitFor(() => fakeApiCall.called);
    wrapper.update();

    const file = { id: 123 };

    wrapper.find('FileList').prop('onSelectFile')(file);
    wrapper.update();

    wrapper.find('LabeledButton[data-testid="select"]').prop('onClick')();

    assert.calledWith(onSelectFile, file);
  });

  it('does not render anything while fetching', async () => {
    const wrapper = renderFilePicker();
    assert.isTrue(wrapper.isEmptyRender());

    await waitFor(() => fakeApiCall.called);
    wrapper.update();
    assert.isFalse(wrapper.isEmptyRender());
  });

  describe('when no files are provided', () => {
    beforeEach(() => {
      fakeApiCall = sinon.stub().resolves([]); // no files returned
    });

    it('renders no file message with a help link', async () => {
      const wrapper = renderFilePicker();
      const fileList = await waitForElement(
        wrapper,
        'FileList[isLoading=false]'
      );
      assert.equal(
        fileList.prop('noFilesMessage').props.href,
        'https://fake_help_link'
      );
      // After first file fetch, we're at the top level, so the no-files message
      // should operate in its "course" context
      assert.isFalse(fileList.prop('noFilesMessage').props.inSubfolder);
    });

    it('renders no-file message in folder context if in a subfolder', async () => {
      const wrapper = renderFilePicker({ withBreadcrumbs: true });
      await waitForElement(wrapper, 'FileList[isLoading=false]');

      changePath(wrapper, fakeFolders[0]);
      const fileList = await waitForElement(wrapper, 'FileList');

      // After first file fetch, we're at the top level, so the no-files message
      // should operate in its "course" context
      assert.isTrue(fileList.prop('noFilesMessage').props.inSubfolder);
    });
  });
});
