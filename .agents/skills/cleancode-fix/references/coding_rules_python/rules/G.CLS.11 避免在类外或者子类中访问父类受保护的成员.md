# G.CLS.11 避免在类外或者子类中访问父类受保护的成员

- **规则ID**：5a794851-ff7d-47e3-a5f4-cbe05f58c13b
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

被`__`双下划线修饰为private类型，那么这就代表着设计者仅允许在本类中使用此属性，不希望外界访问。

被`_`单下划线修饰为protected类型，那么这就代表着设计者仅允许在本类或继承关系中使用，不希望这个属性被外界直接访问(这里的外界概念包含且不限于类方法之外访问，类方法之内跨实例直接访问)。



因此，考虑到不破坏封装性，不建议进行以下操作：

- 不建议在外界直接访问protected类实例属性；

- 不建议使用名字改写特性（name mangling）直接访问private类实例属性。



应该在封装设计的前提下，合理地提供方法访问被保护的类实例属性。

**【正确示例】**

```
##### 场景1：类外或者子类中访受保护的成员
- 修复示例1：protected类型的成员可以在继承关系中被继承，并以方法的形式提供外部访问功能
```python
class Entity:
    def __init__(self, eid: int = 0, race: str = "no name", age: int = 0):
        self.__eid = eid
        self._race = race
        self.age = age


class EntityA(Entity):
    def get_race(self):
        return self._race  


if __name__ == "__main__":
    obj_a = EntityA(eid=1, race="dog")
    print(obj_a.get_race())  # 符合
```
- 修复示例2：protected类型的成员可以在继承关系中被继承，并以属性的形式提供外部访问功能
```python
class Entity:
    def __init__(self, eid: int = 0, race: str = "no name", age: int = 0):
        self.__eid = eid
        self._race = race
        self.age = age


class EntityA(Entity):
    @property
    def race(self):
        return self._race 


if __name__ == "__main__":
    obj_a = EntityA(eid=1, race="dog")
    print(obj_a.race)  # 符合
```


```
**【错误示例】**

```
##### 场景1：类外或者子类中访受保护的成员
- 错误示例：不建议通过直接访问、跨实例访问的形式访问类的protected类实例属性
```python
class Entity:
    def __init__(self, eid: int = 0, race: str = "no name", age: int = 0):
        self.__eid = eid
        self._race = race
        self.age = age


class EntityA(Entity):
    def copy_race(self, entity_obj: Entity):  
        self._race = entity_obj._race  # 不符合，跨实例访问类的protected类实例属性，W0212: Access to a protected member _race of a client class (protected-access)

    def get_race(self):
        return self._race


if __name__ == "__main__":
    obj_a = EntityA(eid=1, race="dog")
    obj_b = EntityA(eid=2, race="cat")
    obj_b.copy_race(obj_a)
    print(obj_b._race)  # 不符合，直接访问类的protected类实例属性，W0212: Access to a protected member _race of a client class (protected-access)
```
- 错误示例：Python的名字改写特性（name mangling）对private类型设计的类实例属性访问，同样是一种破坏封装的行为，不鼓励。
```python
class Entity:
    def __init__(self, eid: int = 0, race: str = "no name", age: int = 0):
        self.__eid = eid
        self._race = race
        self.age = age


if __name__ == "__main__":
    obj_a = Entity(eid=1, race="dog")
    print(obj_a._Entity__eid)  # 不符合
```


```
**【修复建议】**

可以通过以下方法访问被保护的类实例属性：

1. 在类中定义一个公有成员函数，该函数可以访问类的受保护的成员，以提供外部访问功能。

2. 通过 property 装饰器创建只读属性的形式提供外部访问功能。
