'''
You can run Nose by invoking this package, e.g. from the project root:

    $ python3 -m tests

When invoked this way, Nose will be configured to print out the class name for
each test, which is helpful in this project because we have several test classes
that contain identically named test methods.
'''

import nose
import nose.plugins


class ReportClassName(nose.plugins.Plugin):
    '''
    Modify nose reporting to print class name & method name.

    This is helpful since we have multiple test classes that implement the same
    set of test methods.
    '''

    def describeTest(self, nose_wrapper):
        test = nose_wrapper.test
        doc = test._testMethodDoc
        if doc is None:
            doc = test._testMethodName
        else:
            doc = doc.strip()
        return '[{}] {}'.format(test.__class__.__name__, doc)


if __name__ == '__main__':
    nose.main(addplugins=[ReportClassName()])
