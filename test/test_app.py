# import unittest
#
#
# class MyTestCase(unittest.TestCase):
#     def test_something(self):
#         self.assertEqual(True, False)
#
#
# if __name__ == '__main__':
#     unittest.main()
from app import udp_connect


def test_udp_connect():
    assert udp_connect('1', 'M30') == {'status': 'fail', 'data': 'Connection timed out'}