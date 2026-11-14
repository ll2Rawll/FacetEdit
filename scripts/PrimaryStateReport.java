/* Original development-only metadata reporter for the pinned Mojang 1.21.4
 * server. Obfuscated symbols below are resolved from its official mappings.
 * No Minecraft executable code is included in the application/distribution.
 */
import java.lang.reflect.*;
import java.util.*;
import java.nio.file.*;

public class PrimaryStateReport {
    public static void main(String[] args) throws Exception {
        java.io.PrintStream output=System.out;
        Class.forName("ab").getMethod("a").invoke(null); // SharedConstants.tryDetectVersion
        Class.forName("akx").getMethod("a").invoke(null); // Bootstrap.bootStrap
        Class<?> block=Class.forName("djn"), state=Class.forName("dwy");
        Class<?> getter=Class.forName("dfo"), pos=Class.forName("ji"), direction=Class.forName("jn");
        Object empty=Class.forName("dfy").getField("a").get(null), zero=pos.getField("c").get(null);
        Method byId=block.getMethod("a",int.class), sturdy=state.getMethod("c",getter,pos,direction);
        Method getBlock=state.getMethod("b"), holder=block.getMethod("p");
        Method bind=Class.forName("jr$c").getDeclaredMethod("a",Collection.class);bind.setAccessible(true);
        Method tagKey=Class.forName("axf").getMethod("a",Class.forName("aku"),Class.forName("akv"));
        Method location=Class.forName("akv").getMethod("a",String.class);
        Object registry=Class.forName("mc").getField("f").get(null);
        for(String line:Files.readAllLines(Path.of(args[1]))) {
            String[] fields=line.split(" ");List<Object> tags=new ArrayList<>();
            for(int i=1;i<fields.length;i++)tags.add(tagKey.invoke(null,registry,location.invoke(null,fields[i])));
            bind.invoke(holder.invoke(getBlock.invoke(byId.invoke(null,Integer.parseInt(fields[0])))),tags);
        }
        Object wooden=getBlock.invoke(byId.invoke(null,Integer.parseInt(args[2])));
        Object nether=getBlock.invoke(byId.invoke(null,Integer.parseInt(args[3])));
        Object bars=getBlock.invoke(byId.invoke(null,Integer.parseInt(args[4])));
        Method fence=Class.forName("dmm").getMethod("a",state,boolean.class,direction);
        Method pane=Class.forName("dnq").getMethod("a",state,boolean.class);
        Method exception=block.getMethod("k",state), instrument=state.getMethod("E");
        Method conductor=state.getMethod("d",getter,pos),signal=state.getMethod("p");
        Object fire=Class.forName("djp").getField("cy").get(null);
        Method burns=Class.forName("dmo").getDeclaredMethod("g",state);burns.setAccessible(true);
        Method wire=Class.forName("dpu").getDeclaredMethod("a",state,direction);wire.setAccessible(true);
        Method directionName=direction.getMethod("n"), instrumentName=Class.forName("dxy").getMethod("c");
        String[] faces={"down","up","north","south","west","east"};
        for(int id=0;id<=Integer.parseInt(args[0]);id++) {
            Object value=byId.invoke(null,id);int mask=0,woodMask=0,netherMask=0,paneMask=0,wireMask=0;
            for(Object face:direction.getEnumConstants()) {
                String name=(String)directionName.invoke(face);
                for(int bit=0;bit<faces.length;bit++)
                    if(faces[bit].equals(name)) {
                        boolean solid=(boolean)sturdy.invoke(value,empty,zero,face);
                        if(solid)mask|=1<<bit;
                        if(bit>=2) {
                            if((boolean)fence.invoke(wooden,value,solid,face))woodMask|=1<<bit;
                            if((boolean)fence.invoke(nether,value,solid,face))netherMask|=1<<bit;
                            if((boolean)pane.invoke(bars,value,solid))paneMask|=1<<bit;
                            if((boolean)wire.invoke(null,value,face))wireMask|=1<<bit;
                        }
                    }
            }
            output.println("STATE "+id+" "+mask+" "+exception.invoke(null,value)+" "+instrumentName.invoke(instrument.invoke(value))+" "+woodMask+" "+netherMask+" "+paneMask+" "+conductor.invoke(value,empty,zero)+" "+signal.invoke(value)+" "+burns.invoke(fire,value)+" "+wireMask+" "+wire.invoke(null,value,null));
        }
        Class<?> color=Class.forName("cvn");
        for(Object value:color.getEnumConstants())
            output.println("COLOR "+color.getMethod("b").invoke(value)+" "+color.getMethod("g").invoke(value));
    }
}
