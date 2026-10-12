# G.CLS.09 重写类的魔法函数时必须返回其原型指定的类型

- **规则ID**：10cd0986-9290-4de8-ba70-afda870bbf60
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

类的魔法函数（__len__, __bool__等）可以依赖解释器隐式地辅助完成对象的基本功能。

由于和解释器的框架代码耦合，如果重写类的魔法函数时与其原型返回值不一致，将在很多基本功能中出错（真值判断，比较等）。

如果自行定义了类的魔法函数，那么这些魔法函数必须按照其原型要求返回指定类型的对象。

**【正确示例】**

```
# 【正例1】
class Repostory:

    def __init__(self):
        self.objs_repo = list()

    def __len__(self):
        return len(self.objs_repo) // 10  # __len__应该返回一个非负整数，取整

    def __bool__(self):
        return True if self.objs_repo else False  # __bool__应该返回一个bool类型，True or False

    def __setitem__(self, key, value):
        self.objs_repo.append((key, value))

    def __getitem__(self, index):
        print(index, len(self.objs_repo))
        return None if (index < -len(self.objs_repo) or index >= len(self.objs_repo)) else self.objs_repo[index]

```
**【错误示例】**

```
# 【反例1】
class Repostory:

    def __init__(self):
        self.objs_repo = list()

    def __len__(self):
        return len(self.objs_repo) / 10  # __len__应该返回一个非负整数，此处返回float

    def __bool__(self):
        return len(self.objs_repo)  # __bool__返回要求bool类型，此处返回int

    def __setitem__(self, key, value):
        self.objs_repo.append((key, value))

    def __getitem__(self, index):
        print(index, len(self.objs_repo))
        return None if index >= len(self.objs_repo) else self.objs_repo[index]

repo_obj = Repostory()
repo_obj[0] = "zero"
if len(repo_obj):  # TypeError: 'float' object cannot be interpreted as an integer
    print(repo_obj)

if repo_obj:  # TypeError: __bool__ should return bool, returned int
    print(repo_obj)

```
**【修复建议】**

重写类的魔法方法`__getnewargs_ex__`时返回tuple类型，并且元素是(tuple, dict)类型。
