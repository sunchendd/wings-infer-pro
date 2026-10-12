# G.CLS.08 避免在__init__方法外定义类实例属性

- **规则ID**：9e6fa266-72cc-4d9d-8849-7b5907d0d4e0
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

在其它实例方法中定义`__init__`不包含的新属性在功能上虽然没有问题，但会造成多个类实例属性的存在生命周期不一致，为后续跨方法访问埋下隐患。因此，应避免在`__init__`方法外定义类实例属性。

**【正确示例】**

```
##### 场景1：在其它实例方法中定义__init__不包含的新属性
- 修复示例1：实例方法中使用的类实例属性，可以定义在`__init__`方法中，保证在访问时必然存在，不会出现`AttributeError`异常。
```python
class Coder:
    def __init__(self, key_board="no key_board", mouse="no mouse", headphone="no headphone"):
        self.key_board = key_board
        self.mouse = mouse
        self.headphone = headphone  # 符合

    def obtain_headphone(self, headphone):
        self.headphone = headphone


if __name__ == '__main__':
    coder = Coder(key_board="logitech key_board", mouse="logitech mouse")
    ...
    my_equipments = f'I have got {coder.key_board}, {coder.mouse} and {coder.headphone}.'   # I have got logitech key_board, logitech mouse and no headphone.
    print(my_equipments)
```
- 修复示例2：也可以在`__init__`方法中调用的初始化功能的私有方法。
如下案例，私有方法`_set_headphone 和_headphone_primary_equipment`在` __init__`方法中调用了，可以保证在访问时必然存在，不会出现`AttributeError`异常。
```python
class Coder:
    def __init__(self, key_board="no key_board", mouse="no mouse"):
        self._set_secondary_equipment()
        self._set_primary_equipment(key_board, mouse)  #  符合

    def _set_secondary_equipment(self):
        self.headphone = "no headphone"

    def _set_primary_equipment(self, key_board, mouse):
        self.key_board = key_board
        self.mouse = mouse

    def obtain_headphone(self, headphone):
        self.headphone = headphone
```


```
**【错误示例】**

```
##### 场景1：在其它实例方法中定义__init__不包含的新属性
- 错误示例：headphone`是程序运行时通过调用实例方法`obtain_headphone`为`coder`对象添加的属性。在组织`my_equipments`字符串时，如果没有调用过`obtain_headphone`方法，则很容易出现`AttributeError`异常。
```python
class Coder:
    def __init__(self, key_board="no key_board", mouse="no mouse"):
        self.key_board = key_board
        self.mouse = mouse

    def obtain_headphone(self, headphone):
        self.headphone = headphone  # 不符合


if __name__ == '__main__':
    coder = Coder(key_board="logitech key_board", mouse="logitech mouse")
    my_equipments = f'I have got {coder.key_board}, {coder.mouse} and {coder.headphone}.'  # AttributeError: 'Coder' object has no attribute 'headphone'
    print(my_equipments)
```


```
**【修复建议】**

1. 实例方法中使用的类实例属性，可以定义在`__init__`方法中，保证在访问时必然存在。

2. 也可以在`__init__`方法中调用的初始化功能的私有方法。
