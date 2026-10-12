# G.SER.03 禁止使用yaml模块的load函数

- **规则ID**：41ace087-bd69-4cf2-9185-bc0879be2934
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

严重

**【描述】**

yaml模块在数据序列化和配置文件中使用比较广泛，其在解析数据的时候遇到特定格式的数据类型会自动转换为Python的对象，比如会将时间类型的数据自动转化Python时间对象。这个特点让攻击者有机可乘。因此，禁止使用 yaml模块的load函数加载外部数据，会存在潜在的安全风险。



# PyYAML==3.13 模块的load函数实现

def load(stream, Loader=Loader):

    """

    Parse the first YAML document in a stream

    and produce the corresponding Python object.

    """

    loader = Loader(stream)

    try:

        return loader.get_single_data()

    finally:

        loader.dispose()

PyYAML执行反序列化支持指定不同的加载器。

**【正确示例】**

```
import yaml


poc = "!!python/object/apply:subprocess.check_output [[\"calc.exe\"]]"
# 等价于 yaml.load(poc, Loader=yaml.SafeLoader)
yaml.safe_load(poc)

# 上例中，SafeLoader加载器未定义python/object/apply标签的构造函数导致执行报错，未启动计算器。报错信息如下：
# ...
# yaml.constructor.ConstructorError: could not determine a constructor for the tag 
# 'tag:yaml.org,2002:python/object/apply:subprocess.check_output'
#     in "<unicode string>", line 1, column 1:
#     !!python/object/apply:subprocess ... 
#     ^

```
**【错误示例】**

```
【反例1】
# PyYAML<5.1 版本成功启动计算器
import yaml


poc = "!!python/object/apply:subprocess.check_output [[\"calc.exe\"]]"
# 等价于 yaml.load(poc, Loader=yaml.Loader)
yaml.load(poc)

【反例2】
# PyYAML<5.4 版本成功启动计算器
import yaml


poc = """!!python/object/new:tuple 
    - !!python/object/new:map 
      - !!python/name:eval
      - [ "__import__('os').system('calc.exe')" ]"""

yaml.load(poc)

```
**【修复建议】**

下载PyYAML模块的最新版本，并使用其提供的安全函数：



yaml.load(data, Loader=SafeLoader)

yaml.load_all(data, Loader=SafeLoader)

yaml.safe_load(data)

yaml.safe_load_all(data)

也可使用LibYAML库的CSafeLoader函数。
