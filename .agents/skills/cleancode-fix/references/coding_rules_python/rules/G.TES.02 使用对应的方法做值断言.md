# G.TES.02 使用对应的方法做值断言

- **规则ID**：fba1f329-8fc1-49c3-a362-2261dee309e4
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

对于不同的值做断言，Python单元测试模块unittest中的测试用例类TestCase提供了各种不同的方法，建议使用对应的方法做值断言。

**【正确示例】**

```
##### 场景1：检查布尔值
- 修复示例：使用assertTrue/False来检查布尔值
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_bool_values(self):
        true, false = True, False
        self.assertTrue(true)   # 符合
        self.assertFalse(false)  # 符合
```
##### 场景2：检查None或非None的值
- 修复示例：使用assertIs(Not)None来检查None或非None的值
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_none_and_not_none(self):
        none, not_none = None, ""
        self.assertIsNone(none)     # 符合
        self.assertIsNotNone(not_none)     # 符合
```
##### 场景3：检查对象相等性
- 修复示例：建议使用assert(Not)Equal来检查对象相等性
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_equals_and_not_equals(self):
        value_one, value_two, value_three = 1, 2, 1
        self.assertEqual(value_one, value_three)    # 符合
        self.assertNotEqual(value_two, value_three)    # 符合
```
##### 场景4：检查对象大小
- 修复示例：建议使用assert(Greater|Less|Equal)来检查比较对象大小
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_comparison(self):
        value_one, value_two, value_three, value_four = 1, 2, 1, 4
        self.assertGreater(value_two, value_one)   # 符合
        self.assertEqual(value_one, value_three)   # 符合
        self.assertLess(value_one, value_four)   # 符合
```
##### 场景5：检查对象是否为特定类型的实例
- 修复示例：建议使用assert(Not)IsInstance来检查对象是否为特定类型的实例
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_instance_or_not_is_instance(self):
        value = 1
        self.assertIsInstance(value, int)   # 符合
        self.assertNotIsInstance(value, str)   # 符合
```
##### 场景6：检查对象是否在对应的可迭代对象中
- 修复示例：建议使用assertI(Not)In来检查对象是否在对应的可迭代对象中
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_in_collection(self):
        value, values = 1, [1, 2, 3, 4]
        self.assertIn(value, values)   # 符合
        self.assertNotIn(5, values)   # 符合
```

```
**【错误示例】**

```
##### 场景1：检查布尔值
- 错误示例：使用assertEqual来检查布尔值
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_bool_values(self):
        true, false = True, False
        self.assertEqual(true, True)   # 不符合
        self.assertEqual(false, False)   # 不符合
```
##### 场景2：检查None或非None的值
- 错误示例：使用assertTrue来检查None或非None的值
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_none_and_not_none(self):
        none, not_none = None, ""
        self.assertTrue(none is None)       # 不符合
        self.assertTrue(not_none is not None)     # 不符合
```
##### 场景3：检查对象相等性
- 错误示例：使用assertTrue/assertFalse来检查对象相等性
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_equals_and_not_equals(self):
        value_one, value_two, value_three = 1, 2, 1
        self.assertTrue(value_one == value_three)       # 不符合
        self.assertFalse(value_two == value_three)       # 不符合
```
##### 场景4：检查对象大小
- 错误示例：使用assertTrue来检查比较对象大小
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_comparison(self):
        value_one, value_two, value_three, value_four = 1, 2, 1, 4
        self.assertTrue(value_two > value_one)       # 不符合
        self.assertTrue(value_one == value_three)       # 不符合
        self.assertTrue(value_one < value_four)       # 不符合
```
##### 场景5：检查对象是否为特定类型的实例
- 错误示例：使用assertTrue/assertFalse来检查对象是否为特定类型的实例
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_instance_or_not_is_instance(self):
        value = 1
        self.assertTrue(isinstance(value, int))       # 不符合
        self.assertFalse(isinstance(value, str))       # 不符合
```
##### 场景6：检查对象是否在对应的可迭代对象中
- 错误示例：使用assertTrue来检查对象是否在对应的可迭代对象中
```python
import unittest


class TestCaseDemo(unittest.TestCase):
    def test_object_is_in_collection(self):
        value, values = 1, [1, 2, 3, 4]
        self.assertTrue(value in values)      # 不符合
        self.assertTrue(5 not in values)      # 不符合
```

```
**【修复建议】**

写测试用例时使用unittest模块中对应的方法做值断言。
