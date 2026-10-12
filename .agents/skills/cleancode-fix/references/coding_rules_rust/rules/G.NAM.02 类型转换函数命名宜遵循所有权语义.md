# G.NAM.02 类型转换函数命名宜遵循所有权语义

- **规则ID**：230cf29a-fdf1-4b0c-a356-865da90839d8
- **更新时间**：2026-04-07 04:40:00

---

**【问题级别】**

提示

**【描述】**

以 as_ 和 into_ 作为前缀的类型转换通常是 降低抽象层次 ，要么是查看背后的数据 ( as ) ，要么是分解 (deconstructe) 背后的数据 ( into ) 。

相对来说，以 to_ 作为前缀的类型转换处于同一个抽象层次，但是做了更多的工作。



当一个类型用更高级别的语义 (higher-level semantics) 封装 (wraps) 一个与之有关的值时，应该使用 into_inner() 方法名来取出被封装的值。



这适用于以下封装器：



读取缓存 (BufReader) 、编码或解码 (GzDecoder) 、取出原子 (AtomicBool) 、

或者任何相似的语义 (BufWriter)。

**【正确示例】**

```
```
fn main() {
    struct X();
    static S: &str = "str";

    impl X {
        // 符合：as_ 命名的方法只借用 self
        fn as_str(&self) -> &'static str {
            S
        }
        // 符合：返回值不是借用，且 self 对应的类型不支持 Copy 时，to_ 命名的方法则使用 &self 作为参数
        fn to_my_string(&self) -> String {
            S.to_string()
        }
        // 符合：into_ 命名的方法获取了 self 的所有权
        fn into_my_string(self) -> String {
            S.to_string()
        }
    }
}
```

```
**【错误示例】**

```
```
0fn main() {
    struct X();
    static S: &str = "str";

    impl X {
        // 不符合：as_ 命名的方法不应获取 self 的所有权
        fn as_str(self) -> &'static str {
            S
        }
        // 不符合：当返回值不是借用，to_ 命名的方法不应使用 &mut self 作为参数
        fn to_my_string(&mut self) -> String {
            S.to_string()
        }
        // 不符合：into_ 通常需要获取 self 的所有权
        fn into_my_string(&self) -> String {
            S.to_string()
        }
    }
}
```

```
**【修复建议】**

as_ 命名的方法参数一般使用 &self 或 &mut self

to_ 命名的方法参数一般使用 &mut self, &self (非 Copy 类型) 或 self (Copy 类型)

into_ 命名的方法参数一般使用 self
