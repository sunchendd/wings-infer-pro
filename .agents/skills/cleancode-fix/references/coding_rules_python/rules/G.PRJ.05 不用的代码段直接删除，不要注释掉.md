# G.PRJ.05 不用的代码段直接删除，不要注释掉

- **规则ID**：72053ea2-b68a-41ec-95d0-78a2ec0d9019
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

基于python语言运行时编译的特殊性，如果在提供代码的时候提供的是py文件，该文件中包含被注释掉的代码，当企图恢复使用这段代码时，极有可能引入易被忽略的缺陷；尤其是某些接口函数，

如果不在代码中进行彻底删除，某些本应被屏蔽的功能可能在不知情的情况下就被启用了。另外，同样禁止以False为条件语句或者其他任何形式使之成为无法执行到的无效代码。

**【正确示例】**

```
##### 场景1：被注释的代码
- 修复示例：删除注释的代码
```python
 if __name__ == "__main__":
     if sys.argv[1].startswith('--'):
         option = sys.argv[1][2:]
         if option == "load":
             # 安装应用
             LoadCmd(option, sys.argv[2:3][0])
         elif option == "unload":
             # 卸载应用
             UnloadCmd(sys.argv[2:3][0])
         elif option == "unloadproc":
             # 卸载流程
             UnloadProcessCmd(sys.argv[2:3][0])
         else:
             Loginfo("Command {} is unknown".format(sys.argv[1]))
```

```
**【错误示例】**

```
##### 场景1：被注释的代码
- 错误示例：程序中的两个屏蔽的接口，容易造成不安全的因素，注释及被屏蔽的代码段应该直接删除
```python
if __name__ == "__main__":
    if sys.argv[1].startswith('--'):
        option = sys.argv[1][2:]
        if option == "load":
            # 安装应用
            LoadCmd(option, sys.argv[2:3][0])
        elif option == "unload":
            # 卸载应用
            UnloadCmd(sys.argv[2:3][0])
        elif option == "unloadproc":
            # 卸载流程
            UnloadProcessCmd(sys.argv[2:3][0])
        # elif option == 'active':  不符合，被注释的代码
        #   ActiveCmd(sys.argv[2:3][0])
        # elif option == 'inactive':
        #   InActiveCmd(sys.argv[2:3][0])
        else:
            Loginfo("Command {} is unknown".format(sys.argv[1]))
```

```
**【修复建议】**

对不使用的旧代码应该及时删除，以免暴露程序接口，造成不安全的因素。
