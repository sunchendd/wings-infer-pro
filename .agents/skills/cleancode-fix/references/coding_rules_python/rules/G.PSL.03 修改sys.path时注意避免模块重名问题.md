# G.PSL.03 修改sys.path时注意避免模块重名问题

- **规则ID**：900e5cea-6f96-469f-9ca4-f50267b1e4ee
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

`sys.path`是Python在执行`import`语句时搜索模块使用的路径列表，由当前目录、系统环境变量、库目录、`.pth`文件配置组合拼装而成，直接修改之后将作用于当次Python进程运行生命周期内所有`import`语句。

原则上`sys.path`只应该根据用户的系统配置来生成，默认的`sys.path`应该就可以支持模块的搜索过程，不应该在代码里面直接修改。如果确实需要修改，则需要注意尽量不要影响其它模块搜索`sys.path`的顺序，否则可能导致某些`import`语句因为搜索到了错误的模块，导入不了相应的符号而出现`ImportError`异常。

**【正确示例】**

```
##### 场景1：修改`sys.path`
- 修复示例：使用`append`、`extend`等方法加在`sys.path`最后修改`sys.path`，保证不影响其他标准库、三方包模块加载
```python
import sys
sys.path.append("./local_packages")  # 符合
```

```
**【错误示例】**

```
##### 场景1：修改`sys.path`
- 错误示例：使用sys.path.insert修改`sys.path`
```python
import sys
sys.path.insert(0, "./local_packages")  # 不符合
```

```
**【修复建议】**

用`sys.path.append`代替`sys.path.insert`来避免模块重名问题。
