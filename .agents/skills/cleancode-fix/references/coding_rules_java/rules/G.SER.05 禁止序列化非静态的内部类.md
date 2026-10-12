# G.SER.05 禁止序列化非静态的内部类

- **规则ID**：7e2d6557-f141-46ab-b082-3f19761523e1
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

致命

**【描述】**

内部类是一个没有显示或隐式声明为静态的嵌套类。对内部类（包括本地类和匿名类）进行序列化非常容易出错。

**【正确示例】**

```
public class CWE398_CodeCorrectness_NonStaticInnerClassImplementsSerializable_Good_01 implements Serializable {
    private int accessLevel;

    static class Registrator implements Serializable {
        private String data;

        public Registrator(String data){
            this.data = data;
        }

        public void show(){
            System.out.println(data);
        }
    }
}

```
**【错误示例】**

```
public class CWE398_CodeCorrectness_NonStaticInnerClassImplementsSerializable_Bad_01 implements Serializable {
    private int accessLevel;

    /* POTENTIAL FLAW: 禁止序列化非静态的内部类。 */
    class Registrator implements Serializable {
        private String data;

        public Registrator(String data){
            this.data = data;
        }

        public void show(){
            System.out.println(data);
        }
    }
}

```
**【修复建议】**

在使用内部类时，不应对其进行序列化，否则它们将变为静态嵌套类，由此就不会出现对非静态内部类执行序列化时会出现的问题。如果嵌套类为静态类型，则其本质上与实例变量并无关联（包括外部类的实例变量），并且不会导致对外部类执行序列化。
