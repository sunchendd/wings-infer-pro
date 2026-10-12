# G.MET.01 方法要简短

- **规则ID**：d699505d-20ac-4888-b678-6b145486cdad
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

提示

**【描述】**

方法的参数过多，会使得该方法易于受外部（其他部分的代码）变化的影响，从而影响维护工作，同时也会增大测试的工作量。

建议方法参数不超过5个（默认值，支持动态配置）



当方法参数过多时，应进行合理抽象分层，使用合理的手段重构，以增加代码可读性、可维护性，如下方法可供参考：

1. 对方法进行抽象或重构；

2. 将相关参数合在一起，定义成类，用对象封装；

3. 当构造方法含有多个参数时，尝试建造者（Builder）或工厂模式，JDK源码中有很多示例可供参考，例如Calendar.Builder，HttpClient.Builder。

**【正确示例】**

```
```java
    class Parameters {
        private int var1;
        private int var2;
        private int var3;
        private int var4;
        private int var5;
        private int var6;
    ...
    }
    public void doSomething(Parameters parameters) {
    ...
    }
```

```
**【错误示例】**

```
```java
    public void doSomething(int var1, int var2, int var3, int var4, int var5, int var6) {
    ...
    }
```

```
**【修复建议】**

当方法参数过多时，应进行合理抽象分层，使用合理的手段重构，以增加代码可读性、可维护性，如下方法可供参考：

1. 对方法进行抽象或重构；

2. 将相关参数合在一起，定义成类，用对象封装；

3. 当构造方法含有多个参数时，尝试建造者（Builder）或工厂模式，JDK源码中有很多示例可供参考，例如Calendar.Builder，HttpClient.Builder。
