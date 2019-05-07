import { shallow } from 'enzyme';
import { createElement } from 'preact';

import FileList from '../FileList';

describe('FileList', () => {
  const testFiles = [
    {
      id: 123,
      display_name: 'Test.pdf',
      updated_at: '2019-05-09T17:45:21+00:00Z',
    },
  ];

  const renderFileList = (props = {}) =>
    shallow(<FileList files={testFiles} {...props} />);

  it('renders a table with "Name" and "Last modified" columns', () => {
    const wrapper = renderFileList();
    const columns = wrapper
      .find('Table')
      .prop('columns')
      .map(col => col.label);
    assert.deepEqual(columns, ['Name', 'Last modified']);
  });

  it('renders files with an icon, file name and date', () => {
    const wrapper = renderFileList();
    const renderItem = wrapper.find('Table').prop('renderItem');
    const itemWrapper = shallow(<div>{renderItem(testFiles[0])}</div>);
    const formattedDate = new Date(testFiles[0]).toLocaleDateString();
    assert.equal(
      itemWrapper
        .find('td')
        .at(0)
        .text(),
      testFiles[0].display_name
    );
    assert.equal(
      itemWrapper
        .find('td')
        .at(1)
        .text(),
      formattedDate
    );
  });

  it('shows a loading indicator if `isLoading` is true', () => {
    const wrapper = renderFileList({ isLoading: true });
    assert.isTrue(wrapper.exists('.FileList__spinner'));
  });

  it('does not show a loading indicator if `isLoading` is false', () => {
    const wrapper = renderFileList({ isLoading: false });
    assert.isFalse(wrapper.exists('.FileList__spinner'));
  });
});
